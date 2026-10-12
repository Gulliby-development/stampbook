"""Replay the README example session so the docs cannot drift from the code."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from stampbook import cli

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

HEADINGS = [
    "Install",
    "Commands",
    "Clock and time zone",
    "Database",
    "Exit codes",
    "Development",
]


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _blocks(text: str) -> list[str]:
    return re.findall(r"^```[^\n]*\n(.*?)^```[ \t]*$", text, flags=re.DOTALL | re.MULTILINE)


def _parse(block: str) -> list[tuple[str, str, list[str]]]:
    """Return steps as (kind, payload, expected_lines)."""
    steps: list[tuple[str, str, list[str]]] = []
    for line in block.splitlines():
        if line.startswith("$ "):
            cmd = line[2:]
            if cmd.startswith("export "):
                steps.append(("export", cmd[len("export ") :], []))
            else:
                steps.append(("run", cmd, []))
        else:
            assert steps, "output before first command"
            steps[-1][2].append(line)
    return steps


def test_readme_headings() -> None:
    text = _readme()
    for heading in HEADINGS:
        assert re.search(rf"^##+ {re.escape(heading)}\s*$", text, flags=re.MULTILINE), heading


def test_single_example_block_covers_commands() -> None:
    blocks = _blocks(_readme())
    assert len(blocks) == 1
    steps = _parse(blocks[0])
    commands = [shlex.split(p)[1] for k, p, _ in steps if k == "run"]
    for name in ("start", "stop", "status", "log", "report"):
        assert name in commands
    assert any(line.startswith("stampbook: ") for _, _, out in steps for line in out)


def test_readme_example_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("STAMPBOOK_NOW", raising=False)
    monkeypatch.delenv("STAMPBOOK_DB", raising=False)
    db = str(tmp_path / "docs.db")
    steps = _parse(_blocks(_readme())[0])
    assert steps
    for kind, payload, expected in steps:
        if kind == "export":
            name, _, value = payload.partition("=")
            monkeypatch.setenv(name, value)
            continue
        argv = shlex.split(payload)
        assert argv[0] == "stampbook"
        cli.main(["--db", db, *argv[1:]])
        captured = capsys.readouterr()
        actual = (captured.out + captured.err).splitlines()
        assert actual == expected, payload


def test_license_is_mit() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Permission is hereby granted" in text
