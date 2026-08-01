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
tables in `outputs/`, with no manual steps in between.
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
- **Choice of spatial database engine**: DuckDB with the spatial extension. Chosen over
  PostGIS because it ships as a single embedded file with no server to stand up, which
  matters for "runs end to end with no manual intervention" on any reviewer's machine; chosen
  over plain GeoPackage because DuckDB is a real relational engine that enforces declared
  PRIMARY KEY / FOREIGN KEY constraints and supports RTree spatial indexes, neither of which
  GeoPackage does natively. Confirmed empirically that constraints must be declared inline at
  `CREATE TABLE` time (`ALTER TABLE ADD PRIMARY KEY`/`ADD FOREIGN KEY` are not supported) and
  that RTree indexing requires duckdb ≥1.5.x — see commit history.
- **Coordinate reference system for area/distance work**: EPSG:32632 (WGS84 / UTM Zone 32N).
  The study area's extent (5.58°E–10.88°E) straddles the 6°E UTM zone boundary. Empirically
  tested against a custom Transverse Mercator centered on the area's own centroid, using true
  WGS84 geodesic distance as ground truth (`pyproj.Geod`, 300 random facility pairs): UTM 32N
  mean error 0.027%, max 0.091%; custom TM mean 0.018%, max 0.085% — see
  `outputs/logs/crs_comparison_log.md`. The difference is immaterial (well under 10 m of error
  on a multi-km access threshold), so UTM 32N is used for being standard and independently
  verifiable by anyone with GIS tools, rather than adopting a bespoke projection for no
  measurable accuracy gain.
- **Access measure**: straight-line (Euclidean) 5 km catchment, computed in EPSG:32632.
  Network distance was evaluated using the supplied road network and rejected as the primary
  measure — median facility-to-nearest-road distance is 7.3 km, exceeding the catchment
  threshold itself, so network distance would mostly reflect gaps in a sparse 213-feature
  digitization rather than real accessibility (`outputs/logs/road_network_coverage_log.md`).
  The 5 km threshold is externally grounded (WHO-consistent primary-care catchment guidance)
  and independently consistent with this dataset's own facility spacing (median
  nearest-neighbour distance between facilities: 5.8 km).
- **Population denominator**: `wards.total_population` / `population_under5` from
  `admin_boundaries.gpkg` (confirmed complete, 620/620, vs. 14 nulls in the standalone
  `ward_population.csv` — see `outputs/logs/population_reconciliation_correction.md`).
  Population-weighted coverage assumes population is uniformly distributed within each ward,
  since no gridded population surface was supplied — stated as a simplification, not a claim
  of precision.

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

- Uniform within-ward population distribution assumed; a gridded population surface (e.g.
  WorldPop-style) would sharpen every population-weighted figure in this analysis.
- Straight-line catchment does not account for terrain, rivers, or actual travel time. The
  supplied road network was too sparse (median facility-to-road distance 7.3 km) to
  substitute a credible network-distance measure instead.
- Single cross-sectional snapshot — no trend over time or seasonal variation (e.g. wet-season
  road degradation) is captured.
- 106 facilities have never been assessed for staffing; their true adequacy is unknown, not
  zero. Wards dominated by these facilities are flagged as an assessment gap rather than
  assumed inadequate, but the real state of care there is genuinely unknown from this data.
- The 5 km catchment radius and the 10%/80% ward-classification thresholds are data-grounded
  but remain choices. The underlying continuous measures are retained in
  `data/processed/ward_classification.csv` for anyone who wants to re-cut them differently.
- 7 facilities have a register-vs-score-file coordinate mismatch of 800+ km, resolved in
  favour of the score file's geometry but not independently field-verified — flagged
  individually in `outputs/logs/score_ingestion_log.md` for follow-up.