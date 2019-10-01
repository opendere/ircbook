import sys
from datetime import date

import pytest

from util.dateutils import today, parse_iso_date


def test_today():
    assert (isinstance(today(), date))


def test_parse_iso_date_none():
    try:
        parse_iso_date(None)
        assert False
    except ValueError:
        assert (str(sys.exc_info()[1]) == "No date provided")


def test_parse_iso_date_empty():
    try:
        parse_iso_date("")
        assert False
    except ValueError:
        assert str(sys.exc_info()[1]) == "Date must contain ten characters."


def test_parse_iso_date_invalid_format():
    try:
        parse_iso_date("abcdefghij")
        assert False
    except ValueError:
        assert str(sys.exc_info()[1]) == "Invalid date format: abcdefghij. Must use yyyy-mm-dd."


def test_parse_iso_date_invalid_month():
    try:
        parse_iso_date("2017-20-01")
        assert False
    except ValueError:
        assert str(sys.exc_info()[1]) == "Invalid date format: 2017-20-01. Must use yyyy-mm-dd."


def test_parse_iso_date_february_31():
    with pytest.raises(ValueError):
        parse_iso_date("2017-02-31")


def test_parse_iso_date_valid():
    d = parse_iso_date("2017-02-02")
    assert d.year == 2017
    assert d.month == 2
    assert d.day == 2
