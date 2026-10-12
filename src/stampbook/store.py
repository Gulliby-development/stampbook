"""SQLite persistence for time entries."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self

from .timeutil import (
    DomainError,
    UsageError,
    format_display,
    format_timestamp,
    parse_timestamp,
)

SCHEMA_VERSION = 1
_PROJECT_RE = re.compile(r"[A-Za-z0-9._-]{1,40}")


def validate_project(name: str) -> str:
    if not _PROJECT_RE.fullmatch(name):
        raise UsageError(f"invalid project name: {name}")
    return name


def validate_note(note: str | None) -> str | None:
    if note is None:
        return None
    if len(note) > 200:
        raise UsageError("invalid note: longer than 200 characters")
    if "\n" in note or "\r" in note:
        raise UsageError("invalid note: must be a single line")
    return note


@dataclass(frozen=True)
class Entry:
    id: int
    project: str
    note: str | None
    start: datetime
    end: datetime | None

    def effective_end(self, now: datetime) -> datetime:
        return now if self.end is None else self.end


class Store:
    def __init__(self, path: str | Path) -> None:
        self._conn = None
        try:
            self._conn = sqlite3.connect(str(path))
            self._init_schema()
        except sqlite3.Error as exc:
            self.close()
            raise DomainError(f"cannot open database: {exc}") from None
        except DomainError:
            self.close()
            raise

    def _init_schema(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise DomainError("database is newer than this version")
        if version == 0:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS entries ("
                "id INTEGER PRIMARY KEY, project TEXT NOT NULL, note TEXT, "
                "start TEXT NOT NULL, end TEXT)"
            )
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _row(row: tuple) -> Entry:
        return Entry(
            row[0],
            row[1],
            row[2],
            parse_timestamp(row[3]),
            None if row[4] is None else parse_timestamp(row[4]),
        )

    def running(self) -> Entry | None:
        row = self._conn.execute(
            "SELECT id, project, note, start, end FROM entries "
            "WHERE end IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return None if row is None else self._row(row)

    def start(self, project: str, note: str | None, now: datetime) -> Entry:
        validate_project(project)
        validate_note(note)
        current = self.running()
        if current is not None:
            raise DomainError(
                f"already running: {current.project} since {format_display(current.start)}"
            )
        cur = self._conn.execute(
            "INSERT INTO entries (project, note, start, end) VALUES (?, ?, ?, NULL)",
            (project, note, format_timestamp(now)),
        )
        self._conn.commit()
        return Entry(cur.lastrowid, project, note, now, None)

    def stop(self, now: datetime) -> tuple[Entry, int]:
        """Stop the running entry; return it (with end set) and its seconds."""
        current = self.running()
        if current is None:
            raise DomainError("nothing is running")
        if now < current.start:
            raise DomainError("clock is before the running entry started")
        self._conn.execute(
            "UPDATE entries SET end = ? WHERE id = ?",
            (format_timestamp(now), current.id),
        )
        self._conn.commit()
        stopped = Entry(current.id, current.project, current.note, current.start, now)
        return stopped, int((now - current.start).total_seconds())

    def entries(self) -> list[Entry]:
        rows = self._conn.execute(
            "SELECT id, project, note, start, end FROM entries ORDER BY start, id"
        ).fetchall()
        return [self._row(r) for r in rows]
