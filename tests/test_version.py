"""Regression tests for the global stampbook version option."""

from __future__ import annotations

import ast
import os
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import stampbook
from stampbook.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_version_option_prints_the_name_and_the_version(capsys):
    with (
        patch(
            "stampbook.cli.os.environ.get",
            wraps=os.environ.get,
        ) as environment_get,
        patch("stampbook.cli.Store") as store,
    ):
        assert main(["--version"]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"stampbook {stampbook.__version__}\n"
    assert captured.err == ""
    assert all(
        call.args[0] not in {"STAMPBOOK_NOW", "STAMPBOOK_DB"}
        for call in environment_get.call_args_list
        if call.args
    )
    store.assert_not_called()


def test_version_option_does_not_touch_the_database(capsys, tmp_path):
    database = tmp_path / "new.db"

    with (
        patch(
            "stampbook.cli.os.environ.get",
            wraps=os.environ.get,
        ) as environment_get,
        patch("stampbook.cli.Store") as store,
    ):
        assert main(["--db", str(database), "--version"]) == 0

    captured = capsys.readouterr()
    assert captured.out == f"stampbook {stampbook.__version__}\n"
    assert captured.err == ""
    assert not database.exists()
    assert all(
        call.args[0] not in {"STAMPBOOK_NOW", "STAMPBOOK_DB"}
        for call in environment_get.call_args_list
        if call.args
    )
    store.assert_not_called()


def test_version_option_belongs_to_the_program_not_to_a_command(capsys):
    assert main(["status", "--version"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith("stampbook: error: unrecognized arguments: --version\n")


def test_manifest_reads_the_version_from_the_package():
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "version" not in manifest["project"]
    assert manifest["project"]["dynamic"] == ["version"]
    assert manifest["tool"]["setuptools"]["dynamic"] == {
        "version": {"attr": "stampbook.__version__"}
    }


def test_package_version_is_a_plain_string_literal():
    module = ast.parse(
        (ROOT / "src" / "stampbook" / "__init__.py").read_text(encoding="utf-8")
    )
    assignments = [
        statement
        for statement in module.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
    ]

    assert len(assignments) == 1
    value = assignments[0].value
    assert isinstance(value, ast.Constant)
    assert isinstance(value.value, str)
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value.value)
    assert value.value == stampbook.__version__
