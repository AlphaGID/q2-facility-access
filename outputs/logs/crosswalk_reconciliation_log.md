# LGA to Senatorial District Crosswalk — Reconciliation Log

- `old_2019` sheet found (42 rows). Header cell A1 reads: "SUPERSEDED 2019 LIST. DO NOT USE.". Excluded from processing as instructed by the source file itself.

- Parsed 124 data rows from `Sheet1`, after forward-filling State and Senatorial District and dropping blank spacer rows.


## Duplicate LGA codes

- 2 code(s) appeared as exact repeated rows: ['LGA023', 'LGA032']. Treated as accidental duplication in data entry; extra copies dropped.

- 1 code(s) appeared with genuinely conflicting senatorial district assignments: ['LGA100'].

  - `LGA100`: xlsx gives "Tivbetu North" (remarks: Renamed 2019) vs "Tivbetu Central" (remarks: Transferred, see 2021 gazette). `admin_boundaries.gpkg` (current authoritative boundary layer) has sen_district="Tivbetu North". Resolved to the boundary-layer value; the other xlsx row is treated as superseded/not reflected in the current boundary and flagged here, not deleted.


## Coverage check against `admin_boundaries.gpkg` (121 LGAs)

- In boundary layer but missing from crosswalk: 0 

- In crosswalk but not in boundary layer: 0 

- Final reconciled crosswalk: 121 rows, one per LGA code.
