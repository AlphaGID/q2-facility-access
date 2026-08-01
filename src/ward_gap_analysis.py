"""
Step 8: Ward gap classification.

Classifies every ward into one of five categories, distinguishing "no
facility nearby" from "facility nearby but inadequately staffed" from
"facility nearby but never assessed" -- these are different policy
problems (build vs. staff vs. go assess) and conflating them would be a
real methodological error, not a simplification.

Definitions (grounded in the actual distribution of ward_access.csv --
see chat record / README "Key decisions" for the derivation, not
arbitrary round numbers):

  adequate_share  = pct_pop_adequate_facility / pct_pop_any_facility
  unscored_share  = (pct_pop_any_facility - pct_pop_scored_facility)
                     / pct_pop_any_facility
  (both only defined where pct_pop_any_facility > 0)

  no_facility_nearby                    pct_pop_any_facility == 0
  facility_nearby_assessment_gap        adequate_share <= 0.1 AND unscored_share > 0.5
  facility_nearby_confirmed_inadequate  adequate_share <= 0.1, not assessment-gap
  facility_nearby_mixed_adequacy        0.1 < adequate_share < 0.8
  facility_nearby_adequately_staffed    adequate_share >= 0.8

The 0.1 / 0.8 cut points were chosen because the data itself has a real
concentration there: of 613 wards with any facility access, 132 have
adequate_share <= 0.1 (93 of those exactly 0) and 114 have
adequate_share >= 0.8 -- these are natural clusters in the distribution,
not asserted round numbers.

Output:
  - data/processed/ward_classification.csv
  - outputs/logs/ward_gap_analysis_log.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

import duckdb
import pandas as pd

ADEQUATE_SHARE_LOW = 0.1
ADEQUATE_SHARE_HIGH = 0.8
UNSCORED_SHARE_GAP = 0.5


def classify(row):
    if row.pct_pop_any_facility == 0:
        return "no_facility_nearby"
    adequate_share = row.pct_pop_adequate_facility / row.pct_pop_any_facility
    unscored_share = (row.pct_pop_any_facility - row.pct_pop_scored_facility) / row.pct_pop_any_facility
    if adequate_share <= ADEQUATE_SHARE_LOW:
        if unscored_share > UNSCORED_SHARE_GAP:
            return "facility_nearby_assessment_gap"
        return "facility_nearby_confirmed_inadequate"
    if adequate_share >= ADEQUATE_SHARE_HIGH:
        return "facility_nearby_adequately_staffed"
    return "facility_nearby_mixed_adequacy"


def analyze():
    log = ["# Ward Gap Analysis Log\n"]

    wa = pd.read_csv(config.PROCESSED / "ward_access.csv")
    log.append(f"- Loaded {len(wa)} wards from ward_access.csv (Step 7 output).\n")

    con = duckdb.connect(str(config.DUCKDB_PATH))
    ctx = con.execute("""
        SELECT w.ward_code, l.lga_name, sd.sen_district, s.state_name
        FROM wards w
        JOIN lgas l ON w.lga_code = l.lga_code
        JOIN senatorial_districts sd ON l.sen_code = sd.sen_code
        JOIN states s ON sd.state_code = s.state_code
    """).fetchdf()
    con.close()
    wa = wa.merge(ctx, on="ward_code", how="left")
    n_unmatched = wa.sen_district.isna().sum()
    log.append(f"- Joined lga_name / sen_district / state_name via wards -> lgas -> "
               f"senatorial_districts -> states. {n_unmatched} wards failed to match "
               f"(should be 0, given Step 5's FK constraints already guarantee every "
               f"ward has a valid lga_code).\n")

    wa["adequate_share"] = None
    wa["unscored_share"] = None
    has_any = wa.pct_pop_any_facility > 0
    wa.loc[has_any, "adequate_share"] = (
        wa.loc[has_any, "pct_pop_adequate_facility"] / wa.loc[has_any, "pct_pop_any_facility"]
    )
    wa.loc[has_any, "unscored_share"] = (
        (wa.loc[has_any, "pct_pop_any_facility"] - wa.loc[has_any, "pct_pop_scored_facility"])
        / wa.loc[has_any, "pct_pop_any_facility"]
    )

    wa["access_category"] = wa.apply(classify, axis=1)

    counts = wa.access_category.value_counts()
    log.append(f"\n## Ward classification\n")
    for cat, n in counts.items():
        log.append(f"- {cat}: {n}\n")
    assert counts.sum() == len(wa), "category counts must sum to total ward count"

    # Population-weighted view: how many people fall in each category
    # (only where total_population is known -- see Step 7's null handling).
    has_pop = wa.total_population.notna()
    pop_by_cat = wa.loc[has_pop].groupby("access_category").total_population.sum().astype(int)
    total_known_pop = wa.loc[has_pop].total_population.sum()
    log.append(f"\n## Population by category (of {int(total_known_pop):,} people in wards "
               f"with known population)\n")
    for cat, pop in pop_by_cat.items():
        pct = pop / total_known_pop * 100
        log.append(f"- {cat}: {pop:,} ({pct:.1f}%)\n")

    # Senatorial-district roll-up: preview here, full table built in Step 9.
    sen_summary = wa.groupby("sen_district").agg(
        n_wards=("ward_code", "count"),
        n_no_facility=("access_category", lambda s: (s == "no_facility_nearby").sum()),
        n_confirmed_inadequate=("access_category", lambda s: (s == "facility_nearby_confirmed_inadequate").sum()),
    ).sort_values("n_no_facility", ascending=False)
    log.append(f"\n## Senatorial districts with the most 'no facility nearby' wards "
               f"(preview -- full population-weighted table built in Step 9)\n")
    log.append("\n```\n" + sen_summary.head(10).to_string() + "\n```\n")

    wa.to_csv(config.PROCESSED / "ward_classification.csv", index=False)
    log_path = config.LOGS / "ward_gap_analysis_log.md"
    log_path.write_text("\n".join(log))

    print(f"Wrote {config.PROCESSED / 'ward_classification.csv'} ({len(wa)} rows)")
    print(f"Wrote {log_path}")
    print(f"\n{counts}")


if __name__ == "__main__":
    analyze()
