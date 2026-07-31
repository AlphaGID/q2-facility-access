"""
Pipeline orchestrator. Runs every stage in order, from the raw files in
data/raw/ to the final map, table, and database in outputs/ and
data/processed/, with no manual steps in between.

Usage:
    python src/pipeline.py

Stage order matters: each stage's inputs are either raw files or the
output of an earlier stage.
    1. reconcile_crosswalk   -- LGA/senatorial district crosswalk
    2. clean_facilities      -- facility register coordinate cleaning
    3. ingest_scores         -- MIF/MID personnel scores, geometry reconciliation
    4. crs_comparison        -- supporting analysis for the CRS decision (Step 6)
    5. build_database        -- spatial database (needs 1-3's outputs)
    6. road_network_coverage -- supporting analysis for the access-measure
                                 decision (Step 7); needs the database
    7. compute_access        -- population-weighted access measure; needs the database
    8. ward_gap_analysis     -- ward classification; needs compute_access's output
    9. make_outputs          -- final map + summary table; needs ward_gap_analysis's output

Each stage writes its own log to outputs/logs/; this script only reports
which stage is running and stops immediately, with the original
traceback, if any stage fails -- it does not attempt to continue past a
failure, since every later stage depends on earlier ones.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STAGES = [
    ("1. Crosswalk reconciliation", "reconcile_crosswalk", "reconcile"),
    ("2. Facility register cleaning", "clean_facilities", "clean"),
    ("3. Score ingestion & geometry reconciliation", "ingest_scores", "ingest"),
    ("4. CRS comparison (supporting analysis)", "crs_comparison", "analyze"),
    ("5. Spatial database build", "build_database", "build"),
    ("6. Road network coverage (supporting analysis)", "road_network_coverage", "analyze"),
    ("7. Access measure computation", "compute_access", "compute"),
    ("8. Ward gap classification", "ward_gap_analysis", "analyze"),
]


def run():
    start = time.time()
    for label, module_name, func_name in STAGES:
        print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
        t0 = time.time()
        module = __import__(module_name)
        func = getattr(module, func_name)
        func()
        print(f"[{label} done in {time.time() - t0:.1f}s]")

    print(f"\n{'=' * 70}\n9. Final outputs (map + summary table)\n{'=' * 70}")
    t0 = time.time()
    import make_outputs
    make_outputs.build_table()
    make_outputs.build_map()
    print(f"[Final outputs done in {time.time() - t0:.1f}s]")

    print(f"\n{'=' * 70}")
    print(f"Pipeline complete in {time.time() - start:.1f}s total.")
    print("Outputs:")
    print("  - data/processed/facility_access.duckdb")
    print("  - data/processed/ward_classification.csv")
    print("  - outputs/tables/senatorial_district_summary.csv")
    print("  - outputs/maps/facility_access_map.pdf")
    print("  - outputs/logs/*.md (one per stage)")
    print("  - docs/methodological_note.md (written separately, not regenerated)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    run()
