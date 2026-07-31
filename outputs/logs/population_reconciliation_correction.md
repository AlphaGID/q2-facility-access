# Correction: ward population reconciliation claim

An earlier check compared `ward_population.csv` against the population fields already
present in `admin_boundaries.gpkg`'s `wards` layer and reported them as "identical,
620/620". That was wrong.

The comparison used `pandas`, computing `diff = csv_value - gpkg_value` then
`diff.fillna(0)` before testing `< 0.01`. Where the csv had `NaN` (14 wards) and the gpkg
had a real value, `NaN - value = NaN`, and `fillna(0)` turned that into `0`, which then
read as "no difference". This masked a real discrepancy rather than confirming an
absence of one.

Actual state, re-checked directly against the raw values (not a diff):
- `admin_boundaries.gpkg` `wards.total_population`: complete, 620/620, no nulls.
- `ward_population.csv` `total_population`: 14 nulls (ward codes: W0096, W0139, W0155,
  W0272, W0376, W0226, W0238, W0145, W0269, W0353, W0487, W0527, W0479, W0567).
- `population_source` in the csv IS present for all 14 of those rows even though
  `total_population` is blank, so no information is lost by using the gpkg for
  population and the csv only for the source-methodology label -- which is what the
  pipeline already does (see `build_database.py`, `wards` table construction). No
  pipeline output is actually wrong as a result of this; only the documentation
  claiming the two sources were "identical" was wrong, and is corrected here.
