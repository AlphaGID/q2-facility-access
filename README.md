# Facility Readiness, Accessibility and a Governed Spatial Database

eHealth Africa Technical Assessment — Part 1, Question 2.

## What this answers

Given a facility personnel-adequacy score, this pipeline identifies **where populations are
underserved**, distinguishing wards underserved because no facility is physically near them
from wards underserved because a nearby facility exists but is inadequately staffed. These
require different interventions and the two are kept separate throughout.

## Status

This repository is being built incrementally; each pipeline stage is committed as it is
completed. See commit history for the build order. Sections below marked `[TODO]` are not
yet implemented.

## Repository layout
## Environment

Python 3.11, dependencies pinned in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Reproduce

```bash
python src/pipeline.py
```

This runs every stage in order, from the raw files in `data/raw/` to the final map and
tables in `outputs/`, with no manual steps in between. `[TODO: this orchestrator script
will be added once the individual stages are built and tested.]`

Individual stages can also be run separately during development:

```bash
python -m src.reconcile_crosswalk   # Step 2: LGA -> senatorial district crosswalk
python -m src.clean_facilities      # Step 3: facility register coordinate cleaning
python -m src.ingest_scores         # Step 4: MIF/MID personnel score ingestion
python -m src.build_database        # Step 5: load everything into the spatial DB
python -m src.compute_access        # Step 6-7: CRS projection + access measure
python -m src.ward_gap_analysis     # Step 8: absent-vs-understaffed classification
python -m src.make_outputs          # Step 9: map + summary table
```

## Key decisions

- **MIF datum verification**: `facility_personnel_scores.mif` declares `CoordSys Earth
  Projection 1, 104`. Rather than assume this is WGS84, it was checked directly:
  `fiona.open(...).crs` reports `EPSG:4326`. Confirmed, not assumed.
- **Geometry reconciliation**: where both the register and the MIF score file give
  coordinates for the same facility, the MIF point is used as canonical (see
  `outputs/logs/score_ingestion_log.md`) — it matches the register almost exactly in bulk
  (1,183/1,199 comparable facilities within 1 km) and is demonstrably more reliable on the
  16 facilities where they disagree (9 axis swaps, 7 large digitization errors in the
  register only).
  - **Population source correction**: an earlier check wrongly reported `ward_population.csv`
  and `admin_boundaries.gpkg`'s population figures as identical (a `fillna(0)` masked a real
  gap). Corrected: the csv has 14 nulls the gpkg doesn't have. The gpkg is used as the
  authoritative population source for this reason. See
  `outputs/logs/population_reconciliation_correction.md`.
- Choice of spatial database engine: `[TODO]`
- **Coordinate reference system for area/distance work**: EPSG:32632 (WGS84 / UTM Zone 32N).
  The study area's extent (5.58°E–10.88°E) straddles the 6°E UTM zone boundary. Empirically
  tested against a custom Transverse Mercator centered on the area's own centroid, using true
  WGS84 geodesic distance as ground truth (`pyproj.Geod`, 300 random facility pairs): UTM 32N
  mean error 0.027%, max 0.091%; custom TM mean 0.018%, max 0.085% — see
  `outputs/logs/crs_comparison_log.md`. The difference is immaterial (well under 10 m of error
  on a multi-km access threshold), so UTM 32N is used for being standard and independently
  verifiable by anyone with GIS tools, rather than adopting a bespoke projection for no
  measurable accuracy gain.
- Access measure (catchment / cost-distance / network) and its threshold: `[TODO]`
- Population denominator: `[TODO]`

## Data quality findings

Full detail and counts are in the individual logs under `outputs/logs/`. Summary:

- **18 systematic duplicate facility records** (`HF9#####` re-entries of `HF0#####`), removed —
  `outputs/logs/facility_cleaning_log.md`.
- **Coordinates in 3 mixed formats** (plain, DMS, comma-decimal) in the facility register,
  parsed; 24 facilities had no coordinate at all — `outputs/logs/facility_cleaning_log.md`.
  23 of those 24 were recovered from the personnel score file's independent geometry in Step 4
  (see below), leaving only 1 facility with no usable location anywhere in the data.
- **9 facilities had register longitude/latitude swapped**; corrected using the score file's
  geometry — `outputs/logs/score_ingestion_log.md`.
- **7 facilities had register coordinates hundreds of km outside the country**, not explained
  by a swap; score-file geometry used instead, each flagged individually for field verification
  — `outputs/logs/score_ingestion_log.md`.
- **9 placeholder score rows** (`HF70001`–`HF70009`, "Unnamed facility", all-zero) excluded —
  `outputs/logs/score_ingestion_log.md`.
- **124 facilities (106 after dedup) have no personnel score at all** — never assessed, kept as
  null, not zero — `outputs/logs/score_ingestion_log.md`.
- **`LGA_SEN_Districts.xlsx`**: 2 accidental duplicate rows, 1 genuine conflicting entry
  (resolved against the boundary layer, other variant flagged as superseded) —
  `outputs/logs/crosswalk_reconciliation_log.md`.

## Known limitations

`[TODO]`
