"""Tests for the SQLite store."""

import sqlite3
from datetime import datetime

import pytest

from stampbook.store import Store
from stampbook.timeutil import DomainError, UsageError

T0 = datetime(2024, 3, 5, 9, 0, 0)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


def test_creates_schema_and_user_version(db_path):
    with Store(db_path):
        pass
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        cols = conn.execute("PRAGMA table_info(entries)").fetchall()
    finally:
        conn.close()
    assert [c[1] for c in cols] == ["id", "project", "note", "start", "end"]
    by_name = {c[1]: c for c in cols}
    assert by_name["id"][5] == 1
    assert by_name["project"][3] == 1
    assert by_name["start"][3] == 1
    assert by_name["note"][3] == 0
    assert by_name["end"][3] == 0


def test_reopen_existing_database_keeps_data(db_path):
    with Store(db_path) as store:
        store.start("proj", "hello", T0)
    with Store(db_path) as store:
        running = store.running()
    assert running is not None
    assert running.project == "proj"
    assert running.note == "hello"


def test_newer_database_error(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()
    with pytest.raises(DomainError) as info:
        Store(db_path)
    assert str(info.value) == "database is newer than this version"
    assert info.value.exit_code == 1


def test_start_round_trip(db_path):
    with Store(db_path) as store:
        entry = store.start("proj", "a note", T0)
        assert entry.project == "proj"
        assert entry.start == T0
        assert entry.end is None
        assert store.running() == entry
        assert store.entries() == [entry]


def test_stored_format_and_null_end(db_path):
    with Store(db_path) as store:
        store.start("proj", None, T0)
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT project, note, start, end FROM entries").fetchone()
    finally:
        conn.close()
    assert row == ("proj", None, "2024-03-05T09:00:00", None)


def test_stop_round_trip(db_path):
    end = datetime(2024, 3, 5, 10, 5, 59)
    with Store(db_path) as store:
        store.start("proj", None, T0)
        stopped, seconds = store.stop(end)
        assert seconds == 3959
        assert stopped.end == end
        assert store.running() is None
        entries = store.entries()
    assert len(entries) == 1
    assert entries[0].end == end


def test_one_running_rule(db_path):
    with Store(db_path) as store:
        store.start("proj", "note", T0)
        with pytest.raises(DomainError) as info:
            store.start("other", None, datetime(2024, 3, 5, 9, 30, 0))
        assert str(info.value) == "already running: proj since 2024-03-05 09:00:00"
        assert info.value.exit_code == 1
        assert len(store.entries()) == 1


def test_start_after_stop_allowed(db_path):
    with Store(db_path) as store:
        store.start("a", None, T0)
        store.stop(datetime(2024, 3, 5, 10, 0, 0))
        store.start("b", None, datetime(2024, 3, 5, 10, 0, 0))
        assert store.running().project == "b"
        assert [e.project for e in store.entries()] == ["a", "b"]


def test_stop_nothing_running(db_path):
    with Store(db_path) as store, pytest.raises(DomainError) as info:
        store.stop(T0)
    assert str(info.value) == "nothing is running"
    assert info.value.exit_code == 1


def test_stop_zero_length(db_path):
    with Store(db_path) as store:
        store.start("proj", None, T0)
        stopped, seconds = store.stop(T0)
        assert seconds == 0
        assert stopped.end == T0
        assert store.running() is None


def test_stop_clock_before_start(db_path):
    with Store(db_path) as store:
        store.start("proj", None, T0)
        with pytest.raises(DomainError) as info:
            store.stop(datetime(2024, 3, 5, 8, 59, 59))
        assert str(info.value) == "clock is before the running entry started"
        assert info.value.exit_code == 1
        assert store.running() is not None


def test_entries_ordered_by_start(db_path):
    with Store(db_path) as store:
        store.start("a", None, datetime(2024, 3, 5, 12, 0, 0))
        store.stop(datetime(2024, 3, 5, 13, 0, 0))
        store.start("b", None, datetime(2024, 3, 5, 9, 0, 0))
        store.stop(datetime(2024, 3, 5, 10, 0, 0))
        assert [e.project for e in store.entries()] == ["b", "a"]


@pytest.mark.parametrize("name", ["a b", "", "x" * 41])
def test_invalid_project_name(db_path, name):
    with Store(db_path) as store:
        with pytest.raises(UsageError) as info:
            store.start(name, None, T0)
        assert str(info.value) == f"invalid project name: {name}"
        assert info.value.exit_code == 2
        assert store.running() is None


def test_valid_project_and_note_limits(db_path):
    with Store(db_path) as store:
        entry = store.start("ok.1_-", "n" * 200, T0)
    assert entry.note == "n" * 200


def test_invalid_notes(db_path):
    with Store(db_path) as store:
        with pytest.raises(UsageError) as info:
            store.start("proj", "n" * 201, T0)
        assert str(info.value) == "invalid note: longer than 200 characters"
        with pytest.raises(UsageError) as info:
            store.start("proj", "a\nb", T0)
        assert str(info.value) == "invalid note: must be a single line"
        assert store.running() is None
