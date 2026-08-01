"""
Unit tests for src/ward_gap_analysis.py's classify() function.

Uses small synthetic rows (not the real dataset) to exercise every
category boundary explicitly, including the two cut points that were
set from the data's own distribution (0.1 and 0.8) and the interaction
between adequate_share and unscored_share that separates "confirmed
inadequate" from "assessment gap".
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from ward_gap_analysis import classify


def row(any_pct, scored_pct, adequate_pct):
    return SimpleNamespace(
        pct_pop_any_facility=any_pct,
        pct_pop_scored_facility=scored_pct,
        pct_pop_adequate_facility=adequate_pct,
    )


def test_zero_any_facility_is_no_facility_nearby():
    assert classify(row(0.0, 0.0, 0.0)) == "no_facility_nearby"


def test_zero_adequate_share_with_scored_coverage_is_confirmed_inadequate():
    # any=scored=0.5, adequate=0 -> adequate_share=0, unscored_share=0
    assert classify(row(0.5, 0.5, 0.0)) == "facility_nearby_confirmed_inadequate"


def test_zero_adequate_share_dominated_by_unscored_is_assessment_gap():
    # any=0.5, scored=0.1 -> unscored_share = (0.5-0.1)/0.5 = 0.8 > 0.5
    assert classify(row(0.5, 0.1, 0.0)) == "facility_nearby_assessment_gap"


def test_adequate_share_exactly_at_low_boundary_is_inadequate_not_mixed():
    # adequate_share == 0.1 exactly should fall in the <=0.1 bucket
    assert classify(row(1.0, 1.0, 0.1)) == "facility_nearby_confirmed_inadequate"


def test_adequate_share_just_above_low_boundary_is_mixed():
    assert classify(row(1.0, 1.0, 0.11)) == "facility_nearby_mixed_adequacy"


def test_adequate_share_exactly_at_high_boundary_is_adequate():
    assert classify(row(1.0, 1.0, 0.8)) == "facility_nearby_adequately_staffed"


def test_adequate_share_just_below_high_boundary_is_mixed():
    assert classify(row(1.0, 1.0, 0.79)) == "facility_nearby_mixed_adequacy"


def test_fully_adequate_coverage():
    assert classify(row(0.6, 0.6, 0.6)) == "facility_nearby_adequately_staffed"


def test_unscored_share_boundary_is_exclusive():
    # unscored_share exactly 0.5 should NOT count as "dominant" (rule is > 0.5)
    # any=1.0, scored=0.5 -> unscored_share = 0.5 exactly
    assert classify(row(1.0, 0.5, 0.0)) == "facility_nearby_confirmed_inadequate"
