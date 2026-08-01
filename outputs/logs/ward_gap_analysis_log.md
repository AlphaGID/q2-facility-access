# Ward Gap Analysis Log

- Loaded 620 wards from ward_access.csv (Step 7 output).

- Joined lga_name / sen_district / state_name via wards -> lgas -> senatorial_districts -> states. 0 wards failed to match (should be 0, given Step 5's FK constraints already guarantee every ward has a valid lga_code).


## Ward classification

- facility_nearby_mixed_adequacy: 363

- facility_nearby_confirmed_inadequate: 120

- facility_nearby_adequately_staffed: 118

- facility_nearby_assessment_gap: 12

- no_facility_nearby: 7


## Population by category (of 22,936,947 people in wards with known population)

- facility_nearby_adequately_staffed: 4,227,176 (18.4%)

- facility_nearby_assessment_gap: 279,626 (1.2%)

- facility_nearby_confirmed_inadequate: 3,551,460 (15.5%)

- facility_nearby_mixed_adequacy: 14,702,898 (64.1%)

- no_facility_nearby: 175,787 (0.8%)


## Senatorial districts with the most 'no facility nearby' wards (preview -- full population-weighted table built in Step 9)


```
                 n_wards  n_no_facility  n_confirmed_inadequate
sen_district                                                   
Tivbetu North         46              2                       9
Tivbetu Central       41              2                       8
Supwasa North         26              1                      11
Supwasa South         27              1                       2
Agbzatu Central       39              1                       6
Agbkeko Central       27              0                       3
Agbkeko North         30              0                      18
Agbkeko South         27              0                       6
Agbzatu North         38              0                       6
Agbzatu South         34              0                       8
```
