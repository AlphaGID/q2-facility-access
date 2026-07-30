# Personnel Score Ingestion & Geometry Reconciliation Log

- Loaded 1231 score rows from `.mid`, matched 1:1 in file order to 1231 `Point` geometries in `.mif` (row-order equality asserted).

- Loaded 1328 rows from the cleaned facility register.


## Orphan score rows (no matching facility in register)

- 9 score rows have a facility_id not present in the register: ['HF70001', 'HF70002', 'HF70003', 'HF70004', 'HF70005', 'HF70006', 'HF70007', 'HF70008', 'HF70009'].

- Example: `HF70001`, facility_name="Unnamed facility", all cadre counts and personnel_score=0.0, sen_rank=999. Consistent with placeholder/sentinel rows, not real facilities. Excluded entirely from the joined output.


## Register / score coverage

- 1222 register facilities have a matching score.

- 106 register facilities have no score at all (never assessed — kept with score columns as null, NOT zero).


## Geometry reconciliation against boundary extent lon[5.582,10.883] lat[7.229,11.688]

- 1183 matched facilities: MIF and register agree within 1000 m. MIF point used as canonical (independently collected, and validated as reliable in bulk by this same comparison).

- 9 facilities had register longitude/latitude swapped, confirmed by exact match once swapped, corrected using the MIF point: ['HF00568', 'HF00780', 'HF01277', 'HF00668', 'HF00560', 'HF00904', 'HF00253', 'HF00751', 'HF00341']

- 7 facilities have a large, unexplained mismatch between register and MIF coordinates, outside the real boundary extent in the register. MIF point used as canonical; flagged individually for manual field verification, not silently resolved:

  - HF00724: 881.6 km discrepancy

  - HF00270: 1323.4 km discrepancy

  - HF00595: 1274.5 km discrepancy

  - HF00422: 1264.4 km discrepancy

  - HF01265: 896.7 km discrepancy

  - HF01271: 1081.6 km discrepancy

  - HF00848: 1259.8 km discrepancy


- Of the 106 unscored facilities (no MIF cross-check available), 0 have register coordinates outside the boundary extent: []. No second source exists to correct these; flagged in the output as `geometry_source = 'register_out_of_extent_unverified'` rather than silently trusted or dropped.
