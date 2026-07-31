"""
Step 7: Compute the population-weighted access measure.

Method: straight-line (Euclidean) 5 km catchment, computed in EPSG:32632
(see README "Key decisions" and Step 6). Network distance was evaluated
and rejected as the primary measure -- the supplied road network is too
sparse (median facility-to-nearest-road distance 7.4 km; only 37% of
facilities within 5 km of a mapped road) for network distance to reflect
real accessibility rather than digitization gaps. See
outputs/logs/road_network_coverage_log.md.

The 5 km threshold is externally grounded (WHO-consistent primary-care
catchment guidance) AND checked against this dataset: median nearest-
neighbour spacing between facilities here is 5.8 km, so 5 km is not an
arbitrary import, it roughly matches this system's own facility density.

Three separate catchments are computed per ward, all population-weighted
under a uniform-within-ward population distribution (no gridded/raster
population surface was supplied, so this is the standard simplifying
assumption absent finer data -- stated explicitly, not hidden):

  1. pct_pop_any_facility      -- within 5km of ANY facility with geometry,
                                    regardless of staffing status.
  2. pct_pop_scored_facility   -- within 5km of a facility that HAS a
                                    personnel score (adequate or not).
  3. pct_pop_adequate_facility -- within 5km of a facility classified
                                    adequately staffed per
                                    minimum_staffing_norms.adequacy_rule.

Keeping (1)/(2)/(3) separate (rather than collapsing straight to
adequate-vs-not) is what lets Step 8 distinguish "no facility nearby"
from "facility nearby but never assessed" from "facility nearby and
confirmed understaffed" -- collapsing them here would silently treat
"unknown" as either good or bad.

Adequacy rule (from minimum_staffing_norms.csv, applied per facility_type):
  adequately staffed <=> actual count >= minimum, for every cadre with a
  non-zero minimum for that facility_type.

Output:
  - data/processed/ward_access.csv
  - outputs/logs/access_computation_log.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import duckdb
import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.ops import unary_union

CATCHMENT_KM = 5.0
TARGET_CRS = "EPSG:32632"

CADRE_MAP = {
    "med_officers": "min_medical_officers",
    "nurses_midwives": "min_nurses_midwives",
    "chews": "min_chews",
    "lab_scientists": "min_lab_scientists",
    "pharm_techs": "min_pharmacy_technicians",
}


def load_wards(con):
    df = con.execute("""
        SELECT ward_code, ward_name, lga_code, total_population, population_under5,
               population_source, ST_AsText(geom) AS wkt
        FROM wards
    """).fetchdf()
    df["geometry"] = df.wkt.apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df.drop(columns=["wkt"]), geometry="geometry", crs="EPSG:4326")
    return gdf.to_crs(TARGET_CRS)


def load_facilities(con):
    df = con.execute("""
        SELECT facility_id, facility_name, facility_type, ward_code,
               med_officers, nurses_midwives, chews, lab_scientists, pharm_techs,
               personnel_score, geometry_source, ST_AsText(geom) AS wkt
        FROM facilities
        WHERE geom IS NOT NULL
    """).fetchdf()
    df["geometry"] = df.wkt.apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df.drop(columns=["wkt"]), geometry="geometry", crs="EPSG:4326")
    return gdf.to_crs(TARGET_CRS)


def classify_adequacy(fac, con):
    norms = con.execute("SELECT * FROM minimum_staffing_norms").fetchdf()
    norms_idx = norms.set_index("facility_type")

    def status(row):
        if pd.isna(row.personnel_score):
            return "unscored"
        mins = norms_idx.loc[row.facility_type]
        for actual_col, min_col in CADRE_MAP.items():
            min_required = mins[min_col]
            if min_required > 0 and row[actual_col] < min_required:
                return "inadequate"
        return "adequate"

    fac["adequacy_status"] = fac.apply(status, axis=1)
    return fac


def buffered_union(gdf):
    if len(gdf) == 0:
        return None
    return unary_union(list(gdf.geometry.buffer(CATCHMENT_KM * 1000)))


def coverage_fraction(wards, coverage_geom):
    """Fraction of each ward's area falling inside coverage_geom, under a
    uniform-within-ward population assumption."""
    if coverage_geom is None:
        return pd.Series(0.0, index=wards.index)
    frac = []
    for geom in wards.geometry:
        area = geom.area
        if area == 0:
            frac.append(0.0)
            continue
        inter = geom.intersection(coverage_geom).area
        frac.append(inter / area)
    return pd.Series(frac, index=wards.index)


def compute():
    log = ["# Access Computation Log\n"]
    log.append(f"- Catchment radius: {CATCHMENT_KM} km, computed in {TARGET_CRS}.\n")

    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("LOAD spatial;")

    wards = load_wards(con)
    fac = load_facilities(con)
    log.append(f"- {len(wards)} wards, {len(fac)} facilities with usable geometry loaded "
               f"and reprojected to {TARGET_CRS}.\n")

    fac = classify_adequacy(fac, con)
    status_counts = fac.adequacy_status.value_counts()
    log.append(f"\n## Facility adequacy classification\n")
    for status, n in status_counts.items():
        log.append(f"- {status}: {n}\n")

    any_union = buffered_union(fac)
    scored_union = buffered_union(fac[fac.adequacy_status.isin(["adequate", "inadequate"])])
    adequate_union = buffered_union(fac[fac.adequacy_status == "adequate"])

    wards["pct_pop_any_facility"] = coverage_fraction(wards, any_union)
    wards["pct_pop_scored_facility"] = coverage_fraction(wards, scored_union)
    wards["pct_pop_adequate_facility"] = coverage_fraction(wards, adequate_union)

    # Population-weighted absolute figures, only where population is known.
    has_pop = wards.total_population.notna()
    for col in ["pop_any_facility", "pop_scored_facility", "pop_adequate_facility"]:
        pct_col = "pct_" + col
        wards[col] = None
        wards.loc[has_pop, col] = (
            wards.loc[has_pop, "total_population"] * wards.loc[has_pop, pct_col]
        ).round().astype("Int64")

    n_missing_pop = (~has_pop).sum()
    log.append(f"\n## Population weighting\n")
    log.append(f"- {n_missing_pop} wards have no population figure. Their area-based coverage fractions "
               f"(`pct_pop_*`) are still computed and reported, but the absolute `pop_*` "
               f"columns are left null for these wards rather than assuming a population -- "
               f"they are excluded from any population-weighted summary total, not treated "
               f"as zero.\n")
    log.append(f"- Population-weighting assumes population is uniformly distributed within "
               f"each ward (no gridded population surface was supplied). This is a stated "
               f"simplification, not a claim of precision -- a ward that is 60% covered by "
               f"area is treated as 60% covered by population.\n")

    out = wards.drop(columns="geometry").copy()
    out.to_csv(config.PROCESSED / "ward_access.csv", index=False)

    log_path = config.LOGS / "access_computation_log.md"
    log_path.write_text("\n".join(log))

    print(f"Wrote {config.PROCESSED / 'ward_access.csv'} ({len(out)} rows)")
    print(f"Wrote {log_path}")
    print(f"\nFacility adequacy: {dict(status_counts)}")
    print(out[["pct_pop_any_facility", "pct_pop_scored_facility", "pct_pop_adequate_facility"]].describe())


if __name__ == "__main__":
    compute()
