# Access Computation Log

- Catchment radius: 5.0 km, computed in EPSG:32632.

- 620 wards, 1327 facilities with usable geometry loaded and reprojected to EPSG:32632.


## Facility adequacy classification

- inadequate: 666

- adequate: 556

- unscored: 105


## Population weighting

- 0 wards have no population figure. Their area-based coverage fractions (`pct_pop_*`) are still computed and reported, but the absolute `pop_*` columns are left null for these wards rather than assuming a population -- they are excluded from any population-weighted summary total, not treated as zero.

- Population-weighting assumes population is uniformly distributed within each ward (no gridded population surface was supplied). This is a stated simplification, not a claim of precision -- a ward that is 60% covered by area is treated as 60% covered by population.
