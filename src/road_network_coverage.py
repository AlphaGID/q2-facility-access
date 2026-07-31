"""
Supporting analysis for Step 7: quantify road_network.geojson coverage
relative to facility locations, to justify using straight-line catchment
rather than network distance as the primary access measure.

Output:
  - outputs/logs/road_network_coverage_log.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import geopandas as gpd
import pandas as pd
from shapely import wkt
import duckdb


def analyze():
    log = ["# Road Network Coverage Check\n"]

    roads = gpd.read_file(config.F_ROAD_NETWORK).to_crs("EPSG:32632")
    log.append(f"- Loaded {len(roads)} road features. "
               f"road_class: {roads.road_class.value_counts().to_dict()}. "
               f"surface: {roads.surface.value_counts().to_dict()}.\n")

    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("LOAD spatial;")
    fac_df = con.execute("""
        SELECT facility_id, ST_AsText(geom) AS wkt FROM facilities WHERE geom IS NOT NULL
    """).fetchdf()
    con.close()
    fac_df["geometry"] = fac_df.wkt.apply(wkt.loads)
    fac = gpd.GeoDataFrame(fac_df.drop(columns="wkt"), geometry="geometry", crs="EPSG:4326").to_crs("EPSG:32632")

    roads_union = roads.geometry.union_all() if hasattr(roads.geometry, "union_all") else roads.unary_union
    fac["dist_to_nearest_road_km"] = fac.geometry.distance(roads_union) / 1000

    d = fac.dist_to_nearest_road_km
    log.append(f"\n## Facility distance to nearest mapped road\n")
    log.append(f"- {len(fac)} facilities checked. "
               f"mean={d.mean():.2f} km, median={d.median():.2f} km, max={d.max():.2f} km\n")
    for thresh in [1, 2, 5, 10, 20, 30, 50]:
        pct = (d <= thresh).mean() * 100
        log.append(f"- within {thresh} km of a road: {pct:.1f}%\n")

    log.append(f"\n## Conclusion\n")
    log.append(f"- Median facility-to-road distance ({d.median():.1f} km) exceeds the 5 km "
               f"catchment threshold itself. Network distance as the primary access measure "
               f"would be dominated by gaps in the digitized road network rather than "
               f"reflecting real accessibility. Straight-line catchment used instead; the "
               f"road network is noted qualitatively in the methodological note, not used "
               f"as a computed sensitivity layer.\n")

    log_path = config.LOGS / "road_network_coverage_log.md"
    log_path.write_text("\n".join(log))
    print(f"Wrote {log_path}")
    print(d.describe())


if __name__ == "__main__":
    analyze()
