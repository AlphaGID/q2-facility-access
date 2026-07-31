# Road Network Coverage Check

- Loaded 213 road features. road_class: {'Local': 102, 'Trunk B': 72, 'Trunk A': 39}. surface: {'Paved': 89, 'Earth': 70, 'Gravel': 54}.


## Facility distance to nearest mapped road

- 1327 facilities checked. mean=8.63 km, median=7.33 km, max=37.60 km

- within 1 km of a road: 7.8%

- within 2 km of a road: 15.5%

- within 5 km of a road: 37.3%

- within 10 km of a road: 63.1%

- within 20 km of a road: 93.1%

- within 30 km of a road: 99.7%

- within 50 km of a road: 100.0%


## Conclusion

- Median facility-to-road distance (7.3 km) exceeds the 5 km catchment threshold itself. Network distance as the primary access measure would be dominated by gaps in the digitized road network rather than reflecting real accessibility. Straight-line catchment used instead; the road network is noted qualitatively in the methodological note, not used as a computed sensitivity layer.
