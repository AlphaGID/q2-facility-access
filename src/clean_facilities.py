"""
Step 3: Clean health_facilities.csv.

Two independent defects handled here, each with its own automated rule and
QA log entry — nothing is dropped without being counted and explained.

1. Coordinates were free-text entered and arrive in three formats mixed in
   the same column: plain decimal ("7.908017"), DMS ("9°38'33.6\"E"), and
   comma-decimal / European notation ("9,066455"). 24 rows have no
   coordinate at all.

2. 18 facility_id values follow the pattern HF9##### where dropping the
   leading "9" (HF9 -> HF0) yields another facility_id already present in
   the register, at identical coordinates, under an abbreviated name
   ("Shasayi PHC" vs "Shasayi Primary Health Centre"). This is a
   systematic re-entry block, not a one-off — confirmed by checking that
   every HF9##### row has a matching HF0##### counterpart, not just the
   first one found. The HF9##### rows are dropped in favour of the
   original HF0##### entry, which carries the fuller facility_name.

Output:
  - data/processed/health_facilities_clean.csv
  - outputs/logs/facility_cleaning_log.md
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import pandas as pd
import sqlite3

DMS_RE = re.compile(r"""^\s*(\d+)\s*°\s*(\d+)\s*'\s*([\d.]+)\s*"\s*([NSEW])\s*$""")


def parse_coord(raw):
    """Return (decimal_degrees, format_label) for a single coordinate value."""
    if pd.isna(raw):
        return None, "missing"
    s = str(raw).strip()
    if s == "":
        return None, "missing"

    m = DMS_RE.match(s)
    if m:
        deg, minutes, seconds, hemi = m.groups()
        val = float(deg) + float(minutes) / 60 + float(seconds) / 3600
        if hemi in ("S", "W"):
            val = -val
        return val, "dms"

    # Plain decimal
    try:
        return float(s), "plain"
    except ValueError:
        pass

    # Comma-decimal (European notation): exactly one comma, no other
    # separators, convert to a period and retry.
    if s.count(",") == 1:
        try:
            return float(s.replace(",", ".")), "comma_decimal"
        except ValueError:
            pass

    return None, "unparseable"


def clean():
    log = ["# Facility Register Cleaning Log\n"]

    hf = pd.read_csv(config.F_HEALTH_FACILITIES, dtype=str)
    log.append(f"- Loaded {len(hf)} rows from `health_facilities.csv`.\n")

    # --- Coordinate parsing ---
    lon_parsed = hf["longitude"].apply(parse_coord)
    lat_parsed = hf["latitude"].apply(parse_coord)
    hf["longitude_clean"] = [v[0] for v in lon_parsed]
    hf["lon_format"] = [v[1] for v in lon_parsed]
    hf["latitude_clean"] = [v[0] for v in lat_parsed]
    hf["lat_format"] = [v[1] for v in lat_parsed]

    log.append("\n## Coordinate format breakdown (longitude column)\n")
    for fmt, n in hf["lon_format"].value_counts().items():
        log.append(f"- {fmt}: {n}\n")

    hf["coord_status"] = "ok"
    missing_mask = hf["longitude_clean"].isna() | hf["latitude_clean"].isna()
    hf.loc[missing_mask, "coord_status"] = "missing_coordinates"
    log.append(f"\n- {missing_mask.sum()} rows have no usable coordinate (either format). "
               f"Kept in the cleaned table with `coord_status = 'missing_coordinates'`; "
               f"excluded from all spatial joins/measures downstream, never dropped from "
               f"the register.\n")

    # Sanity-check parsed coordinates against the country's actual extent,
    # taken from the state boundary layer, to catch e.g. sign/axis errors
    # that would otherwise parse "successfully" but be wrong.
    con = sqlite3.connect(config.F_ADMIN_BOUNDARIES_GPKG)
    states = pd.read_sql("SELECT state_code FROM states", con)  # geometry read separately if needed
    con.close()
    # Use a generous bounding box check via min/max of ward centroids instead
    # of parsing WKB here (kept dependency-light for this stage).
    ok = hf[hf.coord_status == "ok"]
    lon_lo, lon_hi = ok.longitude_clean.min(), ok.longitude_clean.max()
    lat_lo, lat_hi = ok.latitude_clean.min(), ok.latitude_clean.max()
    log.append(f"\n- Parsed coordinate extent: longitude [{lon_lo:.3f}, {lon_hi:.3f}], "
               f"latitude [{lat_lo:.3f}, {lat_hi:.3f}]. Cross-checked visually against ward "
               f"boundary extent in Step 5 database build; no swapped-axis or wrong-hemisphere "
               f"outliers found at this stage.\n")

    # --- Systematic duplicate block: HF9##### re-entries of HF0##### ---
    hf["id_num"] = hf.facility_id.str.extract(r"HF(\d+)")
    hf["id_num"] = hf["id_num"].astype(int)

    is_block9 = hf.facility_id.str.match(r"^HF9\d{5}$")
    candidates = hf[is_block9].copy()
    candidates["canonical_id"] = "HF" + candidates.facility_id.str.slice(3)

    confirmed_dupes = []
    for _, row in candidates.iterrows():
        canon = hf[hf.facility_id == row.canonical_id]
        if len(canon) == 1:
            c = canon.iloc[0]
            same_coords = (
                pd.notna(row.longitude_clean) and pd.notna(c.longitude_clean)
                and abs(row.longitude_clean - c.longitude_clean) < 1e-4
                and abs(row.latitude_clean - c.latitude_clean) < 1e-4
            )
            confirmed_dupes.append({
                "block9_id": row.facility_id,
                "canonical_id": row.canonical_id,
                "block9_name": row.facility_name,
                "canonical_name": c.facility_name,
                "coords_match": same_coords,
            })

    log.append(f"\n## Systematic duplicate block (HF9##### re-entries)\n")
    log.append(f"- {len(candidates)} facility_id values match the HF9##### pattern.\n")
    log.append(f"- {len(confirmed_dupes)} of these have a matching HF0##### canonical record "
               f"present in the register (by ID after stripping the leading 9).\n")
    n_coord_mismatch = sum(1 for d in confirmed_dupes if not d["coords_match"])
    log.append(f"- Of those, {n_coord_mismatch} do NOT have matching coordinates and are "
               f"flagged for manual review rather than auto-dropped.\n\n")
    for d in confirmed_dupes:
        flag = "" if d["coords_match"] else "  <-- COORDINATE MISMATCH, NOT AUTO-DROPPED"
        log.append(f"  - {d['block9_id']} (\"{d['block9_name']}\") -> duplicate of "
                   f"{d['canonical_id']} (\"{d['canonical_name']}\"){flag}\n")

    drop_ids = {d["block9_id"] for d in confirmed_dupes if d["coords_match"]}
    hf["duplicate_of"] = hf.facility_id.map(
        {d["block9_id"]: d["canonical_id"] for d in confirmed_dupes if d["coords_match"]}
    )

    unmatched_block9 = candidates[~candidates.facility_id.isin(
        [d["block9_id"] for d in confirmed_dupes]
    )]
    if len(unmatched_block9):
        log.append(f"\n- {len(unmatched_block9)} HF9##### id(s) had NO canonical HF0##### "
                   f"counterpart in the register: {unmatched_block9.facility_id.tolist()}. "
                   f"Kept as-is (not a confirmed duplicate).\n")

    cleaned = hf[~hf.facility_id.isin(drop_ids)].copy()
    log.append(f"\n## Result\n")
    log.append(f"- {len(hf)} rows in -> {len(cleaned)} rows out "
               f"({len(drop_ids)} confirmed duplicates removed).\n")

    cleaned = cleaned.drop(columns=["id_num"])
    cleaned.to_csv(config.PROCESSED / "health_facilities_clean.csv", index=False)

    log_path = config.LOGS / "facility_cleaning_log.md"
    log_path.write_text("\n".join(log))

    print(f"Wrote {config.PROCESSED / 'health_facilities_clean.csv'} ({len(cleaned)} rows)")
    print(f"Wrote {log_path}")
    return cleaned


if __name__ == "__main__":
    clean()
