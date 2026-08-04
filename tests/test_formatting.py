"""Tests for utils/formatting.py"""

from utils.formatting import format_hours_minutes


def test_format_zero():
    assert format_hours_minutes(0) == "0h 0m"

def test_format_seconds_only():
    assert format_hours_minutes(59) == "0h 0m"
    assert format_hours_minutes(60) == "0h 1m"
    assert format_hours_minutes(3599) == "0h 59m"

def test_format_hours_only():
    assert format_hours_minutes(3600) == "1h 0m"
    assert format_hours_minutes(7200) == "2h 0m"

def test_format_mixed():
    assert format_hours_minutes(3661) == "1h 1m"
    assert format_hours_minutes(543210) == "150h 53m"
    assert format_hours_minutes(378 * 3600 + 35 * 60) == "378h 35m"

def test_format_large_value():
    assert format_hours_minutes(1_000_000) == "277h 46m"

def test_format_negative():
    result = format_hours_minutes(-3600)
    assert "h" in result and "m" in result

def test_format_float():
    assert format_hours_minutes(90.5) == "0h 1m"
    assert format_hours_minutes(3661.9) == "1h 1m"
