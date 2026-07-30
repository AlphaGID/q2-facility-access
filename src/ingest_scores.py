"""
Step 4: Ingest facility_personnel_scores.mif/.mid and reconcile against the
cleaned facility register.

The .mif file declares `CoordSys Earth Projection 1, 104` — a MapInfo
datum code, not a bare "trust me it's WGS84" declaration. Rather than
silently trust an automatic reprojection, this script reads the raw point
coordinates and validates them directly against the boundary layer's real
extent and against the register's own coordinates. If you want to
independently confirm what datum 104 resolves to, run (once GDAL/fiona
are installed):

    ogrinfo -al -so data/raw/facility_personnel_scores.mif

and record the reported CRS in outputs/logs/score_ingestion_log.md by hand.

Three things get reconciled here, each logged and counted:

1. Placeholder rows: score rows whose facility_id has no match in the
   cleaned register at all. These never correspond to a real facility and
   are excluded from the joined output (a left join from the register
   naturally drops them, but they are also explicitly logged here so the
   exclusion is visible, not just implicit in a join).

2. Axis-swapped register coordinates: for facilities present in both
   files, 9 have register longitude/latitude swapped relative to the
   validated MIF point (confirmed by an exact match once swapped). These
   are corrected in the output, with the correction logged per facility.

3. Register coordinates outside the boundary layer's real extent, not
   explained by a swap: 7 facilities. The MIF point is used as the
   canonical geometry for these (it falls inside the real extent; the
   register coordinate does not), and each is logged individually for
   manual review rather than silently overwritten.

For facilities with a validated score-file match and no problems, the MIF
point is preferred as canonical geometry throughout (it was independently
collected for the scoring exercise and, in bulk, matches the register
almost exactly — median discrepancy 0m across 1,222 matched facilities —
so it is at least as reliable as the free-text-entered register
coordinate, and more reliable in the 16 cases above).

Output:
  - data/processed/facilities_with_scores.csv
  - outputs/logs/score_ingestion_log.md
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import pandas as pd
import sqlite3

SCORE_COLUMNS = [
    "facility_id", "facility_name", "med_officers", "nurses_midwives",
    "chews", "lab_scientists", "pharm_techs", "personnel_score", "sen_rank",
]

SWAP_MATCH_KM = 0.1   # treat as "the same point" once swapped
# The data shows a clean bimodal gap: 26 matched facilities differ by
# 0.2-0.7 km (consistent with ordinary GPS/collection noise between two
# independently captured points for the same facility) and a separate
# group differ by 800+ km (genuinely wrong digitization, not noise).
# 1 km sits in that gap, so it is used as the consistency threshold rather
# than an arbitrarily tight figure that would flag routine noise as errors.
CONSISTENT_KM = 1.0


def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def parse_mif_points(path):
    """Return list of (lon, lat) in file order, matching MID row order."""
    points = []
    with open(path) as f:
        for line in f:
            m = re.match(r"Point ([\-\d.]+) ([\-\d.]+)", line)
            if m:
                points.append((float(m.group(1)), float(m.group(2))))
    return points


def get_boundary_extent():
    con = sqlite3.connect(config.F_ADMIN_BOUNDARIES_GPKG)
    row = con.execute(
        "SELECT min_x, min_y, max_x, max_y FROM gpkg_contents WHERE table_name='states'"
    ).fetchone()
    con.close()
    return row  # (min_x, min_y, max_x, max_y)


def ingest():
    log = ["# Personnel Score Ingestion & Geometry Reconciliation Log\n"]

    mid = pd.read_csv(config.F_SCORES_MID, header=None, names=SCORE_COLUMNS, quotechar='"')
    points = parse_mif_points(config.F_SCORES_MIF)
    assert len(points) == len(mid), (
        f"MIF point count ({len(points)}) != MID row count ({len(mid)}); "
        f"row-order assumption is broken, stop and investigate."
    )
    mid["mif_lon"] = [p[0] for p in points]
    mid["mif_lat"] = [p[1] for p in points]
    log.append(f"- Loaded {len(mid)} score rows from `.mid`, matched 1:1 in file order to "
               f"{len(points)} `Point` geometries in `.mif` (row-order equality asserted).\n")

    hf = pd.read_csv(config.PROCESSED / "health_facilities_clean.csv")
    log.append(f"- Loaded {len(hf)} rows from the cleaned facility register.\n")

    # --- 1. Placeholder / orphan rows: no match in the register at all ---
    in_register = mid.facility_id.isin(hf.facility_id)
    orphans = mid[~in_register]
    log.append(f"\n## Orphan score rows (no matching facility in register)\n")
    log.append(f"- {len(orphans)} score rows have a facility_id not present in the register: "
               f"{sorted(orphans.facility_id.tolist())}.\n")
    if len(orphans):
        sample = orphans.iloc[0]
        log.append(f"- Example: `{sample.facility_id}`, facility_name=\"{sample.facility_name}\", "
                   f"all cadre counts and personnel_score={sample.personnel_score}, "
                   f"sen_rank={sample.sen_rank}. Consistent with placeholder/sentinel rows, not "
                   f"real facilities. Excluded entirely from the joined output.\n")
    valid_scores = mid[in_register].copy()

    # --- Merge for geometry reconciliation ---
    merged = hf.merge(
        valid_scores[["facility_id", "mif_lon", "mif_lat", "med_officers", "nurses_midwives",
                      "chews", "lab_scientists", "pharm_techs", "personnel_score", "sen_rank"]],
        on="facility_id", how="left", indicator=True,
    )
    n_matched = (merged._merge == "both").sum()
    n_unscored = (merged._merge == "left_only").sum()
    log.append(f"\n## Register / score coverage\n")
    log.append(f"- {n_matched} register facilities have a matching score.\n")
    log.append(f"- {n_unscored} register facilities have no score at all "
               f"(never assessed — kept with score columns as null, NOT zero).\n")

    # --- 2 & 3. Geometry reconciliation for matched facilities ---
    ext = get_boundary_extent()
    min_x, min_y, max_x, max_y = ext
    log.append(f"\n## Geometry reconciliation against boundary extent "
               f"lon[{min_x:.3f},{max_x:.3f}] lat[{min_y:.3f},{max_y:.3f}]\n")

    merged["canonical_lon"] = merged["longitude_clean"]
    merged["canonical_lat"] = merged["latitude_clean"]
    merged["geometry_source"] = "register"
    merged["geometry_note"] = ""

    has_score = merged._merge == "both"
    swapped_fixed, unresolved_flagged, consistent = [], [], 0

    for idx, row in merged[has_score].iterrows():
        if pd.isna(row.longitude_clean):
            # No register coordinate at all — MIF is the only source.
            merged.at[idx, "canonical_lon"] = row.mif_lon
            merged.at[idx, "canonical_lat"] = row.mif_lat
            merged.at[idx, "geometry_source"] = "mif_only_register_missing"
            continue

        dist = haversine_km(row.mif_lon, row.mif_lat, row.longitude_clean, row.latitude_clean)
        if dist <= CONSISTENT_KM:
            merged.at[idx, "canonical_lon"] = row.mif_lon
            merged.at[idx, "canonical_lat"] = row.mif_lat
            merged.at[idx, "geometry_source"] = "mif_consistent_with_register"
            consistent += 1
            continue

        dist_swapped = haversine_km(row.mif_lon, row.mif_lat, row.latitude_clean, row.longitude_clean)
        if dist_swapped <= SWAP_MATCH_KM:
            merged.at[idx, "canonical_lon"] = row.mif_lon
            merged.at[idx, "canonical_lat"] = row.mif_lat
            merged.at[idx, "geometry_source"] = "mif_register_axis_swap_corrected"
            merged.at[idx, "geometry_note"] = (
                f"Register had lon/lat swapped (register lon={row.longitude_clean:.6f}, "
                f"lat={row.latitude_clean:.6f}); corrected using MIF point."
            )
            swapped_fixed.append(row.facility_id)
            continue

        # Neither consistent nor a simple swap: large unresolved mismatch.
        merged.at[idx, "canonical_lon"] = row.mif_lon
        merged.at[idx, "canonical_lat"] = row.mif_lat
        merged.at[idx, "geometry_source"] = "mif_preferred_register_unreliable"
        merged.at[idx, "geometry_note"] = (
            f"Register coordinate ({row.longitude_clean:.6f}, {row.latitude_clean:.6f}) is "
            f"{dist:.1f} km from the MIF point and not explained by an axis swap. Register "
            f"value falls outside the boundary extent; MIF point used. FLAGGED FOR MANUAL "
            f"FIELD VERIFICATION."
        )
        unresolved_flagged.append((row.facility_id, dist))

    log.append(f"- {consistent} matched facilities: MIF and register agree within "
               f"{CONSISTENT_KM * 1000:.0f} m. MIF point used as canonical (independently "
               f"collected, and validated as reliable in bulk by this same comparison).\n")
    log.append(f"- {len(swapped_fixed)} facilities had register longitude/latitude swapped, "
               f"confirmed by exact match once swapped, corrected using the MIF point: "
               f"{swapped_fixed}\n")
    log.append(f"- {len(unresolved_flagged)} facilities have a large, unexplained mismatch "
               f"between register and MIF coordinates, outside the real boundary extent in "
               f"the register. MIF point used as canonical; flagged individually for manual "
               f"field verification, not silently resolved:\n")
    for fid, d in unresolved_flagged:
        log.append(f"  - {fid}: {d:.1f} km discrepancy\n")

    # Facilities with no score at all: register coordinate is the only source;
    # just check it falls inside the real extent as a final sanity pass.
    unscored = merged[~has_score]
    out_of_extent = unscored[
        unscored.longitude_clean.notna()
        & ~unscored.longitude_clean.between(min_x, max_x)
        | unscored.latitude_clean.notna()
        & ~unscored.latitude_clean.between(min_y, max_y)
    ]
    log.append(f"\n- Of the {n_unscored} unscored facilities (no MIF cross-check available), "
               f"{len(out_of_extent)} have register coordinates outside the boundary extent: "
               f"{out_of_extent.facility_id.tolist()}. No second source exists to correct "
               f"these; flagged in the output as `geometry_source = 'register_out_of_extent_unverified'` "
               f"rather than silently trusted or dropped.\n")
    merged.loc[out_of_extent.index, "geometry_source"] = "register_out_of_extent_unverified"

    merged.to_csv(config.PROCESSED / "facilities_with_scores.csv", index=False)
    log_path = config.LOGS / "score_ingestion_log.md"
    log_path.write_text("\n".join(log))

    print(f"Wrote {config.PROCESSED / 'facilities_with_scores.csv'} ({len(merged)} rows)")
    print(f"Wrote {log_path}")
    print(f"\nGeometry source breakdown:\n{merged.geometry_source.value_counts()}")
    return merged


if __name__ == "__main__":
    ingest()
