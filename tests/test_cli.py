"""End-to-end tests for the stampbook command line."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from stampbook.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db(tmp_path):
    return tmp_path / "t.db"


@pytest.fixture
def run(capsys, monkeypatch, db):
    monkeypatch.delenv("STAMPBOOK_DB", raising=False)

    def _run(now, *args, use_db=True):
        monkeypatch.setenv("STAMPBOOK_NOW", now)
        argv = ["--db", str(db), *args] if use_db else list(args)
        code = main(argv)
        cap = capsys.readouterr()
        return code, cap.out, cap.err

    return _run


def _populate(run):
    run("2024-03-04T22:00:00", "start", "prev")
    run("2024-03-05T00:00:00", "stop")
    run("2024-03-05T00:00:00", "start", "zero", "-m", "z")
    run("2024-03-05T00:00:00", "stop")
    run("2024-03-05T09:00:00", "start", "work", "-m", "hello")
    run("2024-03-05T10:05:00", "stop")
    run("2024-03-05T23:30:00", "start", "run")


def test_pyproject_and_help():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["stampbook"] == "stampbook.cli:main"
    assert (ROOT / "src" / "stampbook").is_dir()
    assert data["tool"]["pytest"]["ini_options"]["pythonpath"] == ["src"]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    proc = subprocess.run(
        [sys.executable, "-m", "stampbook", "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    assert "stampbook" in proc.stdout


def test_start_stop_status(run):
    assert run("2024-03-05T09:00:00", "status") == (0, "idle\n", "")
    assert run("2024-03-05T09:00:00", "start", "proj", "-m", "note") == (
        0,
        "started proj at 2024-03-05 09:00:00\n",
        "",
    )
    assert run("2024-03-05T10:05:00", "status") == (
        0,
        "running: proj since 2024-03-05 09:00:00 (1h 05m)\n",
        "",
    )
    assert run("2024-03-05T10:05:59", "stop") == (
        0,
        "stopped proj after 1h 05m\n",
        "",
    )
    assert run("2024-03-05T10:06:00", "status")[1] == "idle\n"


def test_start_while_running(run):
    run("2024-03-05T09:00:00", "start", "proj")
    code, out, err = run("2024-03-05T09:30:00", "start", "other")
    assert code == 1
    assert out == ""
    assert err == "stampbook: already running: proj since 2024-03-05 09:00:00\n"


def test_stop_errors(run):
    assert run("2024-03-05T09:00:00", "stop") == (
        1,
        "",
        "stampbook: nothing is running\n",
    )
    run("2024-03-05T09:00:00", "start", "proj")
    assert run("2024-03-05T08:59:59", "stop") == (
        1,
        "",
        "stampbook: clock is before the running entry started\n",
    )
    assert run("2024-03-05T09:00:00", "status")[1].startswith("running:")
    assert run("2024-03-05T09:00:00", "stop") == (
        0,
        "stopped proj after 0m\n",
        "",
    )


def test_log_day(run):
    _populate(run)
    code, out, _ = run("2024-03-05T23:45:00", "log", "--day", "2024-03-05")
    assert code == 0
    assert out == (
        "00:00 00:00 zero 0m # z\n"
        "09:00 10:05 work 1h 05m # hello\n"
        "23:30 ... run 15m\n"
    )
    # default day is the current clock day
    assert run("2024-03-05T23:45:00", "log")[1] == out
    prev = run("2024-03-05T23:45:00", "log", "--day", "2024-03-04")[1]
    assert prev == "22:00 00:00 prev 2h 00m\n"


def test_log_empty(run):
    assert run("2024-03-05T09:00:00", "log", "--day", "2024-03-05") == (
        0,
        "No entries on 2024-03-05\n",
        "",
    )
    assert run("2024-03-05T09:00:00", "log")[1] == "No entries on 2024-03-05\n"


def test_report_sort_padding_total(run):
    _populate(run)
    code, out, _ = run(
        "2024-03-05T23:45:00", "report", "--from", "2024-03-04", "--to", "2024-03-05"
    )
    assert code == 0
    assert out == (
        "prev  2h 00m\n"
        "work  1h 05m\n"
        "run   15m\n"
        "zero  0m\n"
        "Total: 3h 20m\n"
    )


def test_report_default_range_running_entry(run):
    _populate(run)
    code, out, _ = run("2024-03-06T12:00:00", "report")
    assert code == 0
    assert out == (
        "run   12h 30m\n"
        "prev  2h 00m\n"
        "work  1h 05m\n"
        "zero  0m\n"
        "Total: 15h 35m\n"
    )


def test_report_empty_default_range(run):
    assert run("2024-03-06T12:00:00", "report") == (
        0,
        "No entries from 2024-03-04 to 2024-03-06\n",
        "",
    )


def test_report_total_from_seconds_and_name_tie(run):
    run("2024-03-05T09:00:00", "start", "b")
    run("2024-03-05T09:01:30", "stop")
    run("2024-03-05T10:00:00", "start", "a")
    run("2024-03-05T10:01:30", "stop")
    out = run("2024-03-05T12:00:00", "report", "--from", "2024-03-05")[1]
    assert out == "a  1m\nb  1m\nTotal: 3m\n"


def test_report_from_after_to(run):
    assert run(
        "2024-03-06T12:00:00", "report", "--from", "2024-03-06", "--to", "2024-03-05"
    ) == (2, "", "stampbook: --from is after --to\n")


@pytest.mark.parametrize("name", ["a b", "", "x" * 41])
def test_invalid_project(run, name):
    assert run("2024-03-05T09:00:00", "start", name) == (
        2,
        "",
        f"stampbook: invalid project name: {name}\n",
    )


def test_valid_project_and_note_limits(run):
    assert run("2024-03-05T09:00:00", "start", "ok.1_-", "-m", "n" * 200)[0] == 0


def test_invalid_notes(run):
    assert run("2024-03-05T09:00:00", "start", "p", "-m", "n" * 201) == (
        2,
        "",
        "stampbook: invalid note: longer than 200 characters\n",
    )
    assert run("2024-03-05T09:00:00", "start", "p", "-m", "a\nb") == (
        2,
        "",
        "stampbook: invalid note: must be a single line\n",
    )


@pytest.mark.parametrize("bad", ["2023-02-29", "2024-13-01", "2024-2-9"])
@pytest.mark.parametrize("opt", [("log", "--day"), ("report", "--from"), ("report", "--to")])
def test_invalid_dates(run, bad, opt):
    assert run("2024-03-05T09:00:00", *opt, bad) == (
        2,
        "",
        f"stampbook: invalid date: {bad}\n",
    )


def test_leap_date_accepted(run):
    assert run("2024-03-05T09:00:00", "log", "--day", "2024-02-29")[0] == 0


def test_invalid_now(run):
    assert run("garbage", "status") == (
        2,
        "",
        "stampbook: invalid STAMPBOOK_NOW: garbage\n",
    )


def test_newer_database(run, db):
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()
    assert run("2024-03-05T09:00:00", "status") == (
        1,
        "",
        "stampbook: database is newer than this version\n",
    )


def test_schema_created(run, db):
    run("2024-03-05T09:00:00", "status")
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        cols = [r[1] for r in conn.execute("PRAGMA table_info(entries)")]
    finally:
        conn.close()
    assert cols == ["id", "project", "note", "start", "end"]


def _projects(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT project FROM entries")]
    finally:
        conn.close()


def test_db_precedence(run, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = tmp_path / "a.db"
    b = tmp_path / "b.db"
    monkeypatch.setenv("STAMPBOOK_DB", str(a))
    assert run("2024-03-05T09:00:00", "--db", str(b), "start", "inb", use_db=False)[0] == 0
    assert _projects(b) == ["inb"]
    assert not a.exists()
    assert run("2024-03-05T09:00:00", "start", "ina", use_db=False)[0] == 0
    assert _projects(a) == ["ina"]
    monkeypatch.delenv("STAMPBOOK_DB")
    assert run("2024-03-05T09:00:00", "start", "indef", use_db=False)[0] == 0
    assert _projects(tmp_path / "stampbook.db") == ["indef"]


def test_empty_db_values_are_unset(run, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STAMPBOOK_DB", "")
    assert run("2024-03-05T09:00:00", "--db", "", "start", "p", use_db=False)[0] == 0
    assert _projects(tmp_path / "stampbook.db") == ["p"]


@pytest.mark.parametrize(
    "args", [["bogus"], ["start"], [], ["log", "--nope"]]
)
def test_argparse_errors(run, args):
    code, out, err = run("2024-03-05T09:00:00", *args)
    assert code == 2
    assert out == ""
    assert err


def test_no_traceback_on_errors(run):
    for args in (["stop"], ["start", "a b"], ["log", "--day", "x"]):
        _, _, err = run("2024-03-05T09:00:00", *args)
        assert "Traceback" not in err
        assert err.startswith("stampbook: ")
        assert err.count("\n") == 1
