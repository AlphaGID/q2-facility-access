# CRS Comparison: UTM Zone 32N vs Custom Transverse Mercator

- Study area extent (admin_boundaries.gpkg states bbox): lon[5.5818, 10.8831], lat[7.2293, 11.6880].

- Centroid: (8.2324, 9.4587) -- used as the origin for the custom TM, computed from the data rather than hardcoded.


- Custom TM proj4: `+proj=tmerc +lat_0=9.458658 +lon_0=8.232448 +k=1 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs`

- Using 1327 facilities with valid coordinates as the point pool.


## Empirical distance-error comparison, 300 random facility pairs

- UTM Zone 32N: mean abs error 0.0266%, max abs error 0.0911%

- Custom TM (centered on AOI): mean abs error 0.0176%, max abs error 0.0849%


- Conclusion: both are effectively exact at this scale (sub-0.2% error even at max, translating to well under 10 m of error on a multi-km access threshold). UTM 32N is kept as the operational CRS for its standardness and independent verifiability; the custom TM is documented here as the quantified alternative, not because it was needed.
