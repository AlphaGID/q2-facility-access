# Spatial Database Build Log

- Removed existing database file to rebuild from scratch (idempotent run).


## Boundary layers (from admin_boundaries.gpkg, EPSG:4326)

- states: 6, senatorial_districts: 18, lgas: 121, wards: 620. PK on each *_code, FK chain wards -> lgas -> senatorial_districts -> states enforced.

- `wards.population_source` merged in from `ward_population.csv`. Correction: an earlier check wrongly reported this csv's population figures as identical to the gpkg's; the csv actually has 14 nulls in total_population that the gpkg does not. The gpkg is used as the authoritative, complete population source; only population_source is taken from the csv. See outputs/logs/population_reconciliation_correction.md.


## minimum_staffing_norms
- 5 rows, PK facility_type.


## lga_senatorial_crosswalk (audit trail, Step 2 output)
- 121 rows, PK lga_code. Not used operationally (the `lgas` table's sen_code, taken directly from the boundary layer, is what facilities/wards actually join against) -- kept as the documented, automated transformation of the source spreadsheet, per the task requirement, with its full reconciliation log in outputs/logs/crosswalk_reconciliation_log.md.


## facilities

- 1328 rows loaded, PK facility_id, FK facility_type -> minimum_staffing_norms.

- 1327 have a usable geometry; 1 carry NULL geometry (the 24 rows flagged `coord_status='missing_coordinates'` back in Step 3 -- kept as attribute-only rows, never dropped, but necessarily excluded from every spatial operation below and in Steps 6-8).


## Spatial ward assignment (point-in-polygon, ST_Within)

- 1327 facilities assigned to a ward by falling inside its polygon.

- 0 facilities have valid geometry but fall outside every ward polygon (edge-of-boundary digitization gaps). Nearest-ward fallback applied below rather than left unassigned.


## Cross-check: spatial ward assignment vs. stated ward_name

- Of 1327 spatially assigned facilities, 0 have a `ward_name_stated` that does not match (after normalizing case/hyphens/spaces) the ward the point actually falls in. Not auto-corrected, listed below for review.


## Spatial indexes
- RTree index created on the geometry column of every table (states, senatorial_districts, lgas, wards, facilities).
