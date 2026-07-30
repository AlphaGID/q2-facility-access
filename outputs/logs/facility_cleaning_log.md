# Facility Register Cleaning Log

- Loaded 1346 rows from `health_facilities.csv`.


## Coordinate format breakdown (longitude column)

- plain: 1297

- missing: 24

- comma_decimal: 14

- dms: 11


- 24 rows have no usable coordinate (either format). Kept in the cleaned table with `coord_status = 'missing_coordinates'`; excluded from all spatial joins/measures downstream, never dropped from the register.


- Parsed coordinate extent: longitude [-4.375, 19.692], latitude [6.804, 11.658]. Cross-checked visually against ward boundary extent in Step 5 database build; no swapped-axis or wrong-hemisphere outliers found at this stage.


## Systematic duplicate block (HF9##### re-entries)

- 18 facility_id values match the HF9##### pattern.

- 18 of these have a matching HF0##### canonical record present in the register (by ID after stripping the leading 9).

- Of those, 0 do NOT have matching coordinates and are flagged for manual review rather than auto-dropped.


  - HF900919 ("Shasayi PHC") -> duplicate of HF00919 ("Shasayi Primary Health Centre")

  - HF900253 ("Ngemiba Health Post") -> duplicate of HF00253 ("Ngemiba Health Post")

  - HF900014 ("Yellali PHC") -> duplicate of HF00014 ("Yellali Primary Health Centre")

  - HF901326 ("Agbsaja PHC") -> duplicate of HF01326 ("Agbsaja Primary Health Centre")

  - HF900254 ("Agbmade PHC") -> duplicate of HF00254 ("Agbmade Primary Health Centre")

  - HF900512 ("Oluyota PHC") -> duplicate of HF00512 ("Oluyota Primary Health Centre")

  - HF900825 ("Sokbawo PHC") -> duplicate of HF00825 ("Sokbawo Primary Health Centre")

  - HF900431 ("Yobtifa Cottage Hospital") -> duplicate of HF00431 ("Yobtifa Cottage Hospital")

  - HF901211 ("Kuktiru Health Post") -> duplicate of HF01211 ("Kuktiru Health Post")

  - HF901077 ("Birdeli PHC") -> duplicate of HF01077 ("Birdeli Primary Health Centre")

  - HF900899 ("Maltita Health Post") -> duplicate of HF00899 ("Maltita Health Post")

  - HF900052 ("Adetija PHC") -> duplicate of HF00052 ("Adetija Primary Health Centre")

  - HF900565 ("Uzokele Health Post") -> duplicate of HF00565 ("Uzokele Health Post")

  - HF900541 ("Iroyoshi Health Post") -> duplicate of HF00541 ("Iroyoshi Health Post")

  - HF900035 ("Shayosa PHC") -> duplicate of HF00035 ("Shayosa Primary Health Centre")

  - HF901045 ("Uzotsiru Cottage Hospital") -> duplicate of HF01045 ("Uzotsiru Cottage Hospital")

  - HF900507 ("Yelrili PHC") -> duplicate of HF00507 ("Yelrili Primary Health Centre")

  - HF900771 ("Irolata Health Post") -> duplicate of HF00771 ("Irolata Health Post")


## Result

- 1346 rows in -> 1328 rows out (18 confirmed duplicates removed).
