"""Command-line interface for stampbook."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime

from .store import Store, validate_note, validate_project
from .timeutil import (
    StampbookError,
    UsageError,
    clipped_seconds,
    format_clock,
    format_display,
    format_duration,
    monday_of,
    overlaps,
    parse_date,
    parse_now,
    range_bounds,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stampbook", description="Time tracker.")
    parser.add_argument("--db", default=None, help="database path")
    sub = parser.add_subparsers(dest="command", required=True)
    p_start = sub.add_parser("start", help="start tracking a project")
    p_start.add_argument("project")
    p_start.add_argument("-m", "--message", dest="note", default=None)
    sub.add_parser("stop", help="stop the running entry")
    sub.add_parser("status", help="show the running entry")
    p_log = sub.add_parser("log", help="list entries of a day")
    p_log.add_argument("--day", default=None)
    p_log.add_argument("--project", default=None)
    p_rep = sub.add_parser("report", help="totals per project")
    p_rep.add_argument("--from", dest="date_from", default=None)
    p_rep.add_argument("--to", dest="date_to", default=None)
    p_rep.add_argument("--project", default=None)
    return parser


def _now() -> datetime:
    value = os.environ.get("STAMPBOOK_NOW")
    if value:
        return parse_now(value)
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None)


def _db_path(arg: str | None) -> str:
    if arg:
        return arg
    env = os.environ.get("STAMPBOOK_DB")
    if env:
        return env
    return "stampbook.db"


def _cmd_start(store: Store, args: argparse.Namespace, now: datetime) -> None:
    entry = store.start(args.project, args.note, now)
    print(f"started {entry.project} at {format_display(entry.start)}")


def _cmd_stop(store: Store, args: argparse.Namespace, now: datetime) -> None:
    entry, seconds = store.stop(now)
    print(f"stopped {entry.project} after {format_duration(seconds)}")


def _cmd_status(store: Store, args: argparse.Namespace, now: datetime) -> None:
    entry = store.running()
    if entry is None:
        print("idle")
        return
    seconds = max(int((now - entry.start).total_seconds()), 0)
    print(
        f"running: {entry.project} since {format_display(entry.start)} "
        f"({format_duration(seconds)})"
    )


def _cmd_log(store: Store, args: argparse.Namespace, now: datetime) -> None:
    day = args.day_value
    lo, hi = range_bounds(day, day)
    lines = []
    for entry in store.entries():
        if args.project is not None and entry.project != args.project:
            continue
        end = entry.effective_end(now)
        if not overlaps(entry.start, end, lo, hi):
            continue
        seconds = clipped_seconds(entry.start, end, lo, hi)
        end_text = "..." if entry.end is None else format_clock(entry.end)
        line = (
            f"{format_clock(entry.start)} {end_text} "
            f"{entry.project} {format_duration(seconds)}"
        )
        if entry.note:
            line += f" # {entry.note}"
        lines.append(line)
    if not lines:
        if args.project is not None:
            print(f"No entries for {args.project} on {day.isoformat()}")
        else:
            print(f"No entries on {day.isoformat()}")
        return
    print("\n".join(lines))


def _cmd_report(store: Store, args: argparse.Namespace, now: datetime) -> None:
    first, last = args.from_value, args.to_value
    lo, hi = range_bounds(first, last)
    totals: dict[str, int] = {}
    for entry in store.entries():
        if args.project is not None and entry.project != args.project:
            continue
        end = entry.effective_end(now)
        if not overlaps(entry.start, end, lo, hi):
            continue
        seconds = clipped_seconds(entry.start, end, lo, hi)
        totals[entry.project] = totals.get(entry.project, 0) + seconds
    if not totals:
        if args.project is not None:
            print(
                f"No entries for {args.project} from "
                f"{first.isoformat()} to {last.isoformat()}"
            )
        else:
            print(f"No entries from {first.isoformat()} to {last.isoformat()}")
        return
    width = max(len(name) for name in totals)
    for name, seconds in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{name.ljust(width)}  {format_duration(seconds)}")
    print(f"Total: {format_duration(sum(totals.values()))}")


_COMMANDS = {
    "start": _cmd_start,
    "stop": _cmd_stop,
    "status": _cmd_status,
    "log": _cmd_log,
    "report": _cmd_report,
}


def _run(argv: list[str] | None) -> int:
    args = _build_parser().parse_args(argv)
    now = _now()
    if args.command == "start":
        validate_project(args.project)
        validate_note(args.note)
    elif args.command == "log":
        args.day_value = parse_date(args.day) if args.day is not None else now.date()
        if args.project is not None:
            validate_project(args.project)
    elif args.command == "report":
        today: date = now.date()
        first = parse_date(args.date_from) if args.date_from is not None else None
        last = parse_date(args.date_to) if args.date_to is not None else None
        args.from_value = first if first is not None else monday_of(today)
        args.to_value = last if last is not None else today
        if args.from_value > args.to_value:
            raise UsageError("--from is after --to")
        if args.project is not None:
            validate_project(args.project)
    with Store(_db_path(args.db)) as store:
        _COMMANDS[args.command](store, args, now)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except StampbookError as exc:
        print(f"stampbook: {exc}", file=sys.stderr)
        return exc.exit_code
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
