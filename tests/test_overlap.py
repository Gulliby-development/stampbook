"""Tests for the overlap rule, clipping and range helpers."""

from datetime import date, datetime

from stampbook.timeutil import (
    clipped_seconds,
    day_start,
    monday_of,
    overlaps,
    range_bounds,
)


def dt(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S")


DAY = date(2024, 3, 5)
DAY_START, DAY_END = range_bounds(DAY, DAY)
NEXT_START, NEXT_END = range_bounds(date(2024, 3, 6), date(2024, 3, 6))


def test_range_bounds_is_half_open_day():
    assert DAY_START == dt("2024-03-05T00:00:00")
    assert DAY_END == dt("2024-03-06T00:00:00")
    assert day_start(DAY) == DAY_START


def test_entry_inside_day():
    s, e = dt("2024-03-05T09:00:00"), dt("2024-03-05T10:00:00")
    assert overlaps(s, e, DAY_START, DAY_END)
    assert clipped_seconds(s, e, DAY_START, DAY_END) == 3600


def test_crossing_midnight_counts_on_both_days():
    s, e = dt("2024-03-05T23:00:00"), dt("2024-03-06T01:30:00")
    assert overlaps(s, e, DAY_START, DAY_END)
    assert overlaps(s, e, NEXT_START, NEXT_END)
    assert clipped_seconds(s, e, DAY_START, DAY_END) == 3600
    assert clipped_seconds(s, e, NEXT_START, NEXT_END) == 5400


def test_entry_ending_exactly_at_midnight_not_on_next_day():
    s, e = dt("2024-03-05T23:00:00"), dt("2024-03-06T00:00:00")
    assert overlaps(s, e, DAY_START, DAY_END)
    assert not overlaps(s, e, NEXT_START, NEXT_END)
    assert clipped_seconds(s, e, NEXT_START, NEXT_END) == 0


def test_entry_starting_at_day_end_not_in_day():
    s, e = dt("2024-03-06T00:00:00"), dt("2024-03-06T01:00:00")
    assert not overlaps(s, e, DAY_START, DAY_END)


def test_zero_length_entry_on_its_own_day_only():
    t = dt("2024-03-06T00:00:00")
    assert overlaps(t, t, NEXT_START, NEXT_END)
    assert not overlaps(t, t, DAY_START, DAY_END)
    assert clipped_seconds(t, t, NEXT_START, NEXT_END) == 0


def test_zero_length_entry_mid_day():
    t = dt("2024-03-05T12:00:00")
    assert overlaps(t, t, DAY_START, DAY_END)


def test_entry_before_range_not_overlapping():
    s, e = dt("2024-03-04T10:00:00"), dt("2024-03-04T11:00:00")
    assert not overlaps(s, e, DAY_START, DAY_END)


def test_running_entry_uses_now_as_end():
    s, now = dt("2024-03-05T09:00:00"), dt("2024-03-05T10:05:00")
    assert overlaps(s, now, DAY_START, DAY_END)
    assert clipped_seconds(s, now, DAY_START, DAY_END) == 3900


def test_running_entry_clipped_to_range_end():
    s, now = dt("2024-03-05T22:00:00"), dt("2024-03-06T03:00:00")
    assert clipped_seconds(s, now, DAY_START, DAY_END) == 7200


def test_clipping_at_range_edges():
    first, last = date(2024, 3, 4), date(2024, 3, 6)
    lo, hi = range_bounds(first, last)
    s, e = dt("2024-03-03T22:00:00"), dt("2024-03-07T02:00:00")
    assert overlaps(s, e, lo, hi)
    assert clipped_seconds(s, e, lo, hi) == 3 * 86400


def test_monday_of():
    assert monday_of(date(2024, 3, 6)) == date(2024, 3, 4)
    assert monday_of(date(2024, 3, 4)) == date(2024, 3, 4)
    assert monday_of(date(2024, 3, 10)) == date(2024, 3, 4)
