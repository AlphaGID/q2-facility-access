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

`[TODO]` — recorded here as each is made, with the alternatives considered and why they
were rejected:
- Choice of spatial database engine
- Coordinate reference system for area/distance work
- Access measure (catchment / cost-distance / network) and its threshold
- Population denominator

## Data quality findings

`[TODO]` — every defect found, the rule that handles it, and a count of records affected.
Nothing is dropped without a corresponding line here.

## Known limitations

`[TODO]`
