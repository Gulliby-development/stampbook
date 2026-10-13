"""Regression tests for exact project filtering in log and report."""

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


def _populate(run):
    commands = [
        ("2024-03-04T22:00:00", "start", "prev"),
        ("2024-03-05T00:00:00", "stop"),
        ("2024-03-05T00:00:00", "start", "zero", "-m", "z"),
        ("2024-03-05T00:00:00", "stop"),
        ("2024-03-05T09:00:00", "start", "work", "-m", "hello"),
        ("2024-03-05T10:05:00", "stop"),
        ("2024-03-05T23:30:00", "start", "run"),
    ]
    for now, *args in commands:
        assert run(now, *args)[0] == 0


def test_log_filters_exact_projects_and_preserves_unfiltered_output(run):
    _populate(run)
    now = "2024-03-05T23:45:00"
    day = ("--day", "2024-03-05")

    assert run(now, "log", *day) == (
        0,
        (
            "00:00 00:00 zero 0m # z\n"
            "09:00 10:05 work 1h 05m # hello\n"
            "23:30 ... run 15m\n"
        ),
        "",
    )
    assert run(now, "log", *day, "--project", "work") == (
        0,
        "09:00 10:05 work 1h 05m # hello\n",
        "",
    )
    assert run(now, "log", *day, "--project", "run") == (
        0,
        "23:30 ... run 15m\n",
        "",
    )
    assert run(now, "log", *day, "--project", "zero") == (
        0,
        "00:00 00:00 zero 0m # z\n",
        "",
    )

    for project in ("prev", "Work", "nope"):
        assert run(now, "log", *day, "--project", project) == (
            0,
            f"No entries for {project} on 2024-03-05\n",
            "",
        )


def test_report_filters_exact_projects_and_preserves_unfiltered_output(run):
    _populate(run)
    now = "2024-03-05T23:45:00"
    dates = ("--from", "2024-03-04", "--to", "2024-03-05")

    assert run(now, "report", *dates) == (
        0,
        (
            "prev  2h 00m\n"
            "work  1h 05m\n"
            "run   15m\n"
            "zero  0m\n"
            "Total: 3h 20m\n"
        ),
        "",
    )
    assert run(now, "report", *dates, "--project", "prev") == (
        0,
        ("prev  2h 00m\n" "Total: 2h 00m\n"),
        "",
    )
    assert run(now, "report", *dates, "--project", "work") == (
        0,
        ("work  1h 05m\n" "Total: 1h 05m\n"),
        "",
    )
    assert run(now, "report", "--project", "nope") == (
        0,
        "No entries for nope from 2024-03-04 to 2024-03-05\n",
        "",
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("log", "--project", "a b"), "stampbook: invalid project name: a b\n"),
        (("log", "--project", ""), "stampbook: invalid project name: \n"),
        (
            ("report", "--project", "x" * 41),
            f"stampbook: invalid project name: {'x' * 41}\n",
        ),
        (
            ("log", "--day", "bad", "--project", "a b"),
            "stampbook: invalid date: bad\n",
        ),
        (
            (
                "report",
                "--from",
                "2024-03-06",
                "--to",
                "2024-03-05",
                "--project",
                "a b",
            ),
            "stampbook: --from is after --to\n",
        ),
    ],
)
def test_invalid_project_errors_and_date_precedence(run, tmp_path, args, message):
    assert run("2024-03-05T09:00:00", *args) == (2, "", message)
    assert not (tmp_path / "t.db").exists()


@pytest.mark.parametrize("command", ["log", "report"])
def test_project_option_requires_a_value(run, command):
    code, out, err = run("2024-03-05T09:00:00", command, "--project")
    assert code == 2
    assert out == ""
    assert err.startswith("usage: stampbook")


@pytest.mark.parametrize(
    "args",
    [
        ("start", "other", "--project", "other"),
        ("stop", "--project", "other"),
        ("status", "--project", "other"),
    ],
)
def test_project_option_is_limited_to_log_and_report(run, args):
    code, out, err = run("2024-03-05T09:00:00", *args)
    assert code == 2
    assert out == ""
    assert "--project" in err
