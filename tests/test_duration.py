"""Duration formatting tests."""

import pytest

from stampbook.timeutil import format_duration


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0m"),
        (59, "0m"),
        (60, "1m"),
        (119, "1m"),
        (2520, "42m"),
        (3540, "59m"),
        (3599, "59m"),
        (3600, "1h 00m"),
        (3659, "1h 00m"),
        (3900, "1h 05m"),
        (360420, "100h 07m"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_floor_not_round():
    assert format_duration(89) == "1m"
    assert format_duration(3659) == "1h 00m"


def test_total_formatted_from_seconds_not_floored_parts():
    parts = [90, 90]
    assert [format_duration(p) for p in parts] == ["1m", "1m"]
    assert format_duration(sum(parts)) == "3m"
