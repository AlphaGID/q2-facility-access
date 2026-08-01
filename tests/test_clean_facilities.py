"""
Unit tests for src/clean_facilities.py's coordinate parser.

Covers the 3 real formats found in health_facilities.csv, plus edge
cases (missing, unparseable, negative/hemisphere handling in DMS).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from clean_facilities import parse_coord


def test_plain_decimal():
    val, fmt = parse_coord("7.908017")
    assert fmt == "plain"
    assert abs(val - 7.908017) < 1e-9


def test_comma_decimal():
    val, fmt = parse_coord("9,066455")
    assert fmt == "comma_decimal"
    assert abs(val - 9.066455) < 1e-9


def test_dms_east_positive():
    val, fmt = parse_coord("9°38'33.6\"E")
    assert fmt == "dms"
    expected = 9 + 38 / 60 + 33.6 / 3600
    assert abs(val - expected) < 1e-6


def test_dms_south_negative():
    val, fmt = parse_coord("10°02'07.3\"S")
    assert fmt == "dms"
    expected = -(10 + 2 / 60 + 7.3 / 3600)
    assert abs(val - expected) < 1e-6


def test_dms_west_negative():
    val, fmt = parse_coord("6°58'01.8\"W")
    assert fmt == "dms"
    assert val < 0


def test_missing_value_is_none():
    import pandas as pd
    val, fmt = parse_coord(pd.NA)
    assert fmt == "missing"
    assert val is None


def test_empty_string_is_missing():
    val, fmt = parse_coord("")
    assert fmt == "missing"


def test_garbage_is_unparseable():
    val, fmt = parse_coord("not-a-coordinate")
    assert fmt == "unparseable"
    assert val is None


def test_multiple_commas_not_treated_as_comma_decimal():
    # a value with more than one comma should not be silently mangled
    # into a number -- guards against a too-loose comma-decimal rule.
    val, fmt = parse_coord("1,234,567")
    assert fmt == "unparseable"
