# Methodological Note: Facility Readiness, Accessibility, and a Governed Spatial Database

## Question answered

Given a facility personnel-adequacy score, where are populations underserved — and is that
because no facility is physically near them, or because a nearby facility exists but is
inadequately staffed? These require different interventions (construction vs. staffing vs.
assessment), so the pipeline keeps them distinct throughout rather than collapsing to a
single "access" number.

## Data reconciliation (full detail in `outputs/logs/`)

The facility register, personnel scoring file, senatorial-district crosswalk, and boundary
layer did not agree with one another out of the box. Nothing was dropped without being
counted: 18 systematically duplicated facility records (`HF9#####` re-entries of `HF0#####`)
removed; coordinates parsed from 3 mixed formats (plain/DMS/comma-decimal), 24 missing
entirely (23 recovered from the score file's independent geometry, 1 genuinely unlocatable);
9 facilities had register longitude/latitude swapped and 7 had register coordinates hundreds
of km outside the country, both corrected using the score file's cross-validated geometry; 9
placeholder score rows excluded; 106 facilities have never been assessed (kept as null, not
zero); the LGA-senatorial crosswalk had 2 accidental duplicate rows and 1 genuine conflicting
entry, resolved against the boundary layer.

## Database

DuckDB with the spatial extension: an embedded, single-file relational engine that enforces
declared primary/foreign keys and supports RTree spatial indexes, avoiding both the need to
stand up a PostGIS server and GeoPackage's lack of enforced constraints. Facilities are
spatially assigned to wards by point-in-polygon containment (with nearest-ward fallback for
edge-of-boundary cases), independently cross-checked against the register's stated ward name
— 0 mismatches out of 1,327.

## CRS

EPSG:32632 (UTM Zone 32N). The study area straddles the 6°E zone boundary; empirically tested
against a custom Transverse Mercator centered on the area's own centroid using true WGS84
geodesic distance as ground truth (300 random facility pairs): UTM 32N mean error 0.027%
(max 0.091%), custom TM mean 0.018% (max 0.085%). The difference is immaterial at the km-scale
thresholds used here, so the standard, independently-verifiable UTM zone was kept.

## Access measure

Straight-line 5 km catchment. Network distance (using the supplied road network) was
evaluated and rejected as the primary measure: median facility-to-nearest-road distance is
7.3 km — greater than the catchment threshold itself — so network distance would mostly
reflect gaps in a sparse, simplified 213-feature digitization rather than real accessibility.
The 5 km threshold is externally grounded (WHO-consistent primary-care catchment guidance)
and consistent with this dataset's own facility spacing (median nearest-neighbour distance
between facilities: 5.8 km). Population is assumed uniformly distributed within each ward (no
gridded population surface was supplied) — a stated simplification, not a claim of precision.

Adequacy follows `minimum_staffing_norms.adequacy_rule` exactly: a facility is adequately
staffed when actual counts meet or exceed the minimum for every cadre with a non-zero
minimum for its facility type.

## Ward classification (620 wards, 22,936,947 people)

| Category | Wards | Meaning |
|---|---|---|
| No facility within 5km | 7 | Genuinely absent — construction problem |
| Facility nearby, confirmed inadequate | 120 | Assessed and understaffed — staffing problem |
| Facility nearby, assessment gap | 12 | Never assessed — data-collection problem |
| Facility nearby, mixed adequacy | 363 | Partial coverage from a mix of facilities |
| Facility nearby, adequately staffed | 118 | Genuinely well served |

Thresholds for this classification (adequate-coverage share ≤10% / ≥80% of a ward's
facility-accessible population) were set from the data's own distribution — a real
concentration at both ends among the 613 wards with any facility access — not asserted round
numbers (see chat record / commit history for the derivation).

**Headline finding**: only 18.4% of the population is within 5 km of an adequately staffed
facility, against 39.8% within 5 km of *any* facility — the staffing gap, not the physical
access gap, is the larger problem in this dataset. Agbkeko North senatorial district is the
clearest priority: 62.5% of its population sits in confirmed-inadequate-coverage wards, the
highest of any district and with essentially no adequately-staffed reach at all
(see `outputs/tables/senatorial_district_summary.csv`).

## Known limitations

- Uniform within-ward population distribution assumed; a gridded population surface would
  sharpen the population-weighted figures.
- Straight-line catchment does not account for terrain, rivers, or actual travel time; the
  road network was too sparse in this data pack to substitute a network-distance measure
  credibly (see `outputs/logs/road_network_coverage_log.md`).
- Single cross-sectional snapshot; no trend or seasonal variation (e.g. wet-season road
  access) is captured.
- 106 facilities' staffing adequacy is unknown, not zero; wards dominated by these facilities
  are flagged as an assessment gap rather than assumed inadequate, but the true state of care
  in those wards is genuinely unknown from this data.
- The 5 km / 10% / 80% thresholds are defensible and data-grounded but are still choices;
  the underlying continuous measures (`pct_pop_adequate_facility` etc.) are retained in
  `ward_classification.csv` for anyone who wants to re-cut them.
