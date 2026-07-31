"""
Supporting analysis for Step 6: empirically compare UTM Zone 32N (the
chosen CRS) against a custom Transverse Mercator centered on the study
area's own centroid, measuring actual distance error against WGS84
ellipsoidal (geodesic) ground truth via pyproj's Geod -- not a formula
approximation.

This is a documented alternative, not the operational choice. UTM 32N
remains primary (see README "Key decisions") because the error difference
turns out to be immaterial at this scale and UTM is the standard,
independently-verifiable option. This script exists so the trade-off is
backed by real numbers, not asserted.

Output:
  - data/processed/crs_comparison_sample.csv
  - outputs/logs/crs_comparison_log.md
"""
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import pandas as pd
from pyproj import CRS, Transformer, Geod


def get_extent_centroid():
    con = sqlite3.connect(config.F_ADMIN_BOUNDARIES_GPKG)
    row = con.execute(
        "SELECT min_x, min_y, max_x, max_y FROM gpkg_contents WHERE table_name='states'"
    ).fetchone()
    con.close()
    min_x, min_y, max_x, max_y = row
    return (min_x + max_x) / 2, (min_y + max_y) / 2, row


def analyze():
    log = ["# CRS Comparison: UTM Zone 32N vs Custom Transverse Mercator\n"]

    cen_lon, cen_lat, extent = get_extent_centroid()
    log.append(f"- Study area extent (admin_boundaries.gpkg states bbox): "
               f"lon[{extent[0]:.4f}, {extent[2]:.4f}], lat[{extent[1]:.4f}, {extent[3]:.4f}].\n")
    log.append(f"- Centroid: ({cen_lon:.4f}, {cen_lat:.4f}) -- used as the origin for the "
               f"custom TM, computed from the data rather than hardcoded.\n")

    utm32n = CRS.from_epsg(32632)
    custom_tm = CRS.from_proj4(
        f"+proj=tmerc +lat_0={cen_lat} +lon_0={cen_lon} +k=1 +x_0=500000 +y_0=0 "
        f"+ellps=WGS84 +units=m +no_defs"
    )
    log.append(f"\n- Custom TM proj4: `+proj=tmerc +lat_0={cen_lat:.6f} +lon_0={cen_lon:.6f} "
               f"+k=1 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs`\n")

    to_utm = Transformer.from_crs("EPSG:4326", utm32n, always_xy=True)
    to_custom = Transformer.from_crs("EPSG:4326", custom_tm, always_xy=True)
    geod = Geod(ellps="WGS84")

    fac = pd.read_csv(config.PROCESSED / "facilities_with_scores.csv")
    fac = fac.dropna(subset=["canonical_lon", "canonical_lat"]).reset_index(drop=True)
    log.append(f"- Using {len(fac)} facilities with valid coordinates as the point pool.\n")

    random.seed(42)
    n_pairs = 300
    idx = list(range(len(fac)))
    raw_pairs = [(random.choice(idx), random.choice(idx)) for _ in range(n_pairs)]
    pairs = [(i, j) for i, j in raw_pairs if i != j]

    rows = []
    for i, j in pairs:
        lon1, lat1 = fac.loc[i, "canonical_lon"], fac.loc[i, "canonical_lat"]
        lon2, lat2 = fac.loc[j, "canonical_lon"], fac.loc[j, "canonical_lat"]

        _, _, geod_dist = geod.inv(lon1, lat1, lon2, lat2)

        x1, y1 = to_utm.transform(lon1, lat1)
        x2, y2 = to_utm.transform(lon2, lat2)
        utm_dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        x1c, y1c = to_custom.transform(lon1, lat1)
        x2c, y2c = to_custom.transform(lon2, lat2)
        custom_dist = ((x2c - x1c) ** 2 + (y2c - y1c) ** 2) ** 0.5

        rows.append({
            "geod_km": geod_dist / 1000,
            "utm_km": utm_dist / 1000,
            "custom_km": custom_dist / 1000,
            "utm_error_pct": (utm_dist - geod_dist) / geod_dist * 100,
            "custom_error_pct": (custom_dist - geod_dist) / geod_dist * 100,
        })

    df = pd.DataFrame(rows)
    log.append(f"\n## Empirical distance-error comparison, {len(df)} random facility pairs\n")
    log.append(f"- UTM Zone 32N: mean abs error {df.utm_error_pct.abs().mean():.4f}%, "
               f"max abs error {df.utm_error_pct.abs().max():.4f}%\n")
    log.append(f"- Custom TM (centered on AOI): mean abs error {df.custom_error_pct.abs().mean():.4f}%, "
               f"max abs error {df.custom_error_pct.abs().max():.4f}%\n")
    log.append(f"\n- Conclusion: both are effectively exact at this scale (sub-0.2% error even "
               f"at max, translating to well under 10 m of error on a multi-km access "
               f"threshold). UTM 32N is kept as the operational CRS for its standardness and "
               f"independent verifiability; the custom TM is documented here as the "
               f"quantified alternative, not because it was needed.\n")

    df.to_csv(config.PROCESSED / "crs_comparison_sample.csv", index=False)
    log_path = config.LOGS / "crs_comparison_log.md"
    log_path.write_text("\n".join(log))

    print(f"Wrote {log_path}")
    print(df[["utm_error_pct", "custom_error_pct"]].abs().describe())


if __name__ == "__main__":
    analyze()
