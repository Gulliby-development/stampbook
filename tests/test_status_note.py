"""The status line shows the note of the running entry, as the log line does."""

from __future__ import annotations

import pytest

from stampbook.cli import main


@pytest.fixture
def run(capsys, monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.delenv("STAMPBOOK_DB", raising=False)

    def _run(now, *args):
        monkeypatch.setenv("STAMPBOOK_NOW", now)
        code = main(["--db", str(db), *args])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def test_status_ends_with_the_note_of_the_running_entry(run):
    assert run("2024-03-05T09:00:00", "start", "website", "-m", "landing page")[0] == 0
    assert run("2024-03-05T10:05:00", "status") == (
        0,
        "running: website since 2024-03-05 09:00:00 (1h 05m) # landing page\n",
        "",
    )


def test_status_without_a_note_is_unchanged(run):
    assert run("2024-03-05T09:00:00", "start", "docs")[0] == 0
    assert run("2024-03-05T09:42:30", "status") == (
        0,
        "running: docs since 2024-03-05 09:00:00 (42m)\n",
        "",
    )


def test_status_keeps_a_hash_sign_inside_the_note(run):
    assert run("2024-03-05T09:00:00", "start", "docs", "-m", "fix #12 # again")[0] == 0
    assert run("2024-03-05T09:01:00", "status")[1] == (
        "running: docs since 2024-03-05 09:00:00 (1m) # fix #12 # again\n"
    )


def test_status_of_an_idle_database_stays_idle(run):
    assert run("2024-03-05T09:00:00", "status") == (0, "idle\n", "")
    assert run("2024-03-05T09:00:00", "start", "docs", "-m", "note")[0] == 0
    assert run("2024-03-05T09:30:00", "stop")[0] == 0
    assert run("2024-03-05T09:31:00", "status") == (0, "idle\n", "")


def test_status_note_matches_the_note_in_the_log(run):
    assert run("2024-03-05T09:00:00", "start", "work", "-m", "hello")[0] == 0
    status = run("2024-03-05T09:10:00", "status")[1]
    log = run("2024-03-05T09:10:00", "log")[1]
    assert status.endswith(" # hello\n")
    assert log == "09:00 ... work 10m # hello\n"


def test_start_and_stop_lines_do_not_show_the_note(run):
    assert (
        run("2024-03-05T09:00:00", "start", "work", "-m", "hello")[1]
        == "started work at 2024-03-05 09:00:00\n"
    )
    assert run("2024-03-05T09:10:00", "stop")[1] == "stopped work after 10m\n"
