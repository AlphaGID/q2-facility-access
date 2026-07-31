"""
Step 9: Final outputs -- A3 map and senatorial district summary table.

Map: two panels, side by side, A3 landscape.
  Left:  ward choropleth by access_category (the 5-category classification
         from Step 8) -- the policy-relevant view.
  Right: ward choropleth by pct_pop_adequate_facility (continuous %) --
         the underlying continuous measure the categories were cut from.
Facility points overlaid on both panels, adequate (green) and confirmed
inadequate (red) only -- unscored facilities omitted from the map itself
per design decision (not hidden from the data: they're fully present in
ward_classification.csv and factored into the assessment-gap category;
just visually cluttering on a map already carrying five ward categories).

Table: population-weighted senatorial district summary, ranked by
pct_pop_confirmed_inadequate descending -- surfaces the districts where
the staffing problem (not the construction problem) is most acute.

Output:
  - outputs/maps/facility_access_map.pdf
  - outputs/tables/senatorial_district_summary.csv
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import duckdb
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
from shapely import wkt

CATEGORY_COLORS = {
    "no_facility_nearby": "#4a0d0d",
    "facility_nearby_confirmed_inadequate": "#d7301f",
    "facility_nearby_assessment_gap": "#969696",
    "facility_nearby_mixed_adequacy": "#fdae61",
    "facility_nearby_adequately_staffed": "#1a9850",
}
CATEGORY_LABELS = {
    "no_facility_nearby": "No facility within 5km",
    "facility_nearby_confirmed_inadequate": "Facility nearby, confirmed inadequate",
    "facility_nearby_assessment_gap": "Facility nearby, assessment gap",
    "facility_nearby_mixed_adequacy": "Facility nearby, mixed adequacy",
    "facility_nearby_adequately_staffed": "Facility nearby, adequately staffed",
}


def build_table():
    df = pd.read_csv(config.PROCESSED / "ward_classification.csv")
    d = df[df.total_population.notna()].copy()

    def summarize(g):
        total_pop = g.total_population.sum()
        row = {"n_wards": len(g), "total_population": int(total_pop)}
        for cat in CATEGORY_COLORS:
            pop_in_cat = g.loc[g.access_category == cat, "total_population"].sum()
            row[f"pct_pop_{cat}"] = round(pop_in_cat / total_pop * 100, 1)
        return pd.Series(row)

    summary = d.groupby(["state_name", "sen_district"]).apply(summarize)
    summary = summary.sort_values("pct_pop_facility_nearby_confirmed_inadequate", ascending=False)
    summary = summary.reset_index()
    summary.to_csv(config.TABLES / "senatorial_district_summary.csv", index=False)
    return summary


def load_geometries(con):
    wards_df = con.execute("""
        SELECT ward_code, ST_AsText(geom) AS wkt FROM wards
    """).fetchdf()
    wards_df["geometry"] = wards_df.wkt.apply(wkt.loads)
    wards = gpd.GeoDataFrame(wards_df.drop(columns="wkt"), geometry="geometry", crs="EPSG:4326")

    # Adequacy status isn't stored in the DB (it was computed in-memory in
    # Step 7); recomputed here from the same norms table for the map's
    # facility point symbology.
    fac_df = con.execute("""
        SELECT facility_id, facility_type, med_officers, nurses_midwives, chews,
               lab_scientists, pharm_techs, personnel_score, ST_AsText(geom) AS wkt
        FROM facilities WHERE geom IS NOT NULL
    """).fetchdf()
    fac_df["geometry"] = fac_df.wkt.apply(wkt.loads)
    fac = gpd.GeoDataFrame(fac_df.drop(columns="wkt"), geometry="geometry", crs="EPSG:4326")

    norms = con.execute("SELECT * FROM minimum_staffing_norms").fetchdf().set_index("facility_type")
    cadre_map = {
        "med_officers": "min_medical_officers", "nurses_midwives": "min_nurses_midwives",
        "chews": "min_chews", "lab_scientists": "min_lab_scientists",
        "pharm_techs": "min_pharmacy_technicians",
    }

    def status(row):
        if pd.isna(row.personnel_score):
            return "unscored"
        mins = norms.loc[row.facility_type]
        for actual_col, min_col in cadre_map.items():
            if mins[min_col] > 0 and row[actual_col] < mins[min_col]:
                return "inadequate"
        return "adequate"

    fac["adequacy_status"] = fac.apply(status, axis=1)
    return wards.to_crs("EPSG:32632"), fac.to_crs("EPSG:32632")


def build_map():
    wc = pd.read_csv(config.PROCESSED / "ward_classification.csv")

    con = duckdb.connect(str(config.DUCKDB_PATH))
    con.execute("LOAD spatial;")
    wards, fac = load_geometries(con)
    con.close()

    wards = wards.merge(
        wc[["ward_code", "access_category", "pct_pop_adequate_facility", "ward_name", "total_population"]],
        on="ward_code", how="left",
    )

    fig, axes = plt.subplots(1, 2, figsize=(16.54, 11.69))  # A3 landscape, inches

    # --- Left panel: categorical ---
    ax = axes[0]
    for cat, color in CATEGORY_COLORS.items():
        sub = wards[wards.access_category == cat]
        sub.plot(ax=ax, color=color, edgecolor="white", linewidth=0.2)
    ax.set_title("Ward access classification", fontsize=13, fontweight="bold")
    ax.set_axis_off()
    handles = [mpatches.Patch(color=c, label=CATEGORY_LABELS[k]) for k, c in CATEGORY_COLORS.items()]

    adequate = fac[fac.adequacy_status == "adequate"]
    inadequate = fac[fac.adequacy_status == "inadequate"]
    adequate.plot(ax=ax, color="#1a9850", markersize=6, marker="o", edgecolor="black", linewidth=0.3, zorder=5)
    inadequate.plot(ax=ax, color="#d7301f", markersize=6, marker="^", edgecolor="black", linewidth=0.3, zorder=5)
    handles += [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#1a9850", markeredgecolor="black",
                   markersize=7, label="Facility: adequately staffed"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="#d7301f", markeredgecolor="black",
                   markersize=7, label="Facility: confirmed inadequate"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, frameon=True, title="Legend", title_fontsize=8)

    # --- Right panel: continuous ---
    ax2 = axes[1]
    wards.plot(
        column="pct_pop_adequate_facility", ax=ax2, cmap="RdYlGn", edgecolor="white",
        linewidth=0.2, legend=True,
        legend_kwds={"label": "% of ward population within 5km of an adequately staffed facility",
                     "orientation": "horizontal", "shrink": 0.6, "pad": 0.02},
        vmin=0, vmax=1,
    )
    ax2.set_title("Population-weighted adequate-facility coverage (continuous)", fontsize=13, fontweight="bold")
    ax2.set_axis_off()
    adequate.plot(ax=ax2, color="black", markersize=4, marker="o", alpha=0.5, zorder=5)
    inadequate.plot(ax=ax2, color="black", markersize=4, marker="^", alpha=0.5, zorder=5)

    fig.suptitle(
        "Facility Readiness and Population Access -- 5km straight-line catchment, EPSG:32632\n"
        "Synthetic data, eHealth Africa Technical Assessment Part 1 Q2",
        fontsize=11,
    )
    fig.text(0.5, 0.02,
              "Source: health_facilities.csv, facility_personnel_scores.mif/mid, admin_boundaries.gpkg, "
              "ward_population.csv (synthetic). Unscored facilities omitted from point symbols "
              "(see outputs/logs/ for full accounting); still reflected in the assessment-gap ward category.",
              ha="center", fontsize=7, style="italic")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    out_path = config.MAPS / "facility_access_map.pdf"
    fig.savefig(out_path, format="pdf", dpi=300)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    summary = build_table()
    print(f"Wrote {config.TABLES / 'senatorial_district_summary.csv'} ({len(summary)} rows)")
    map_path = build_map()
    print(f"Wrote {map_path}")
