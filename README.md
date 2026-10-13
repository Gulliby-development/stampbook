<p align="center"><img src="docs/logo.svg" width="96" alt="" /></p>

# stampbook

A small command-line time tracker: start and stop entries per project, stored in a local SQLite file, with totals per project.

[![CI](https://github.com/Gulliby-development/stampbook/actions/workflows/ci.yml/badge.svg)](https://github.com/Gulliby-development/stampbook/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why

You want a simple, scriptable way to see where your time goes, without an account, a service or any dependency. stampbook needs Python 3.11+ and only the standard library, and runs on Windows, macOS and Linux.

## Install

Use a virtual environment so the `stampbook` command stays out of your system Python:

    python -m venv .venv
    . .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install .

This installs the `stampbook` command; `python -m stampbook` works too.

## Usage

### Commands

- `stampbook [--db PATH] start PROJECT [-m NOTE]`
- `stampbook stop`
- `stampbook status`
- `stampbook log [--day YYYY-MM-DD] [--project PROJECT]`
- `stampbook report [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--project PROJECT]`

`--project PROJECT` keeps only the entries of that project (exact, case-sensitive name; same rules as for `start`). Without it, both commands list every project. If nothing matches, the message names the project, for example `No entries for docs on 2024-03-05`.

Example session (the database path is omitted; `$ export` sets the clock):

```
$ export STAMPBOOK_NOW=2024-03-05T09:00:00
$ stampbook status
idle
$ stampbook start website -m "landing page"
started website at 2024-03-05 09:00:00
$ stampbook start docs
stampbook: already running: website since 2024-03-05 09:00:00
$ export STAMPBOOK_NOW=2024-03-05T10:05:00
$ stampbook status
running: website since 2024-03-05 09:00:00 (1h 05m)
$ stampbook stop
stopped website after 1h 05m
$ export STAMPBOOK_NOW=2024-03-05T11:00:00
$ stampbook start docs
started docs at 2024-03-05 11:00:00
$ export STAMPBOOK_NOW=2024-03-05T11:42:30
$ stampbook stop
stopped docs after 42m
$ stampbook log
09:00 10:05 website 1h 05m # landing page
11:00 11:42 docs 42m
$ stampbook report --from 2024-03-04 --to 2024-03-05
website  1h 05m
docs     42m
Total: 1h 47m
$ stampbook log --project website
09:00 10:05 website 1h 05m # landing page
$ stampbook report --from 2024-03-04 --to 2024-03-05 --project docs
docs  42m
Total: 42m
$ stampbook log --project blog
No entries for blog on 2024-03-05
$ stampbook report --from 2024-03-06 --to 2024-03-05
stampbook: --from is after --to
```

## Clock and time zone

All times are UTC, timezone-naive, with whole-second precision. Set the environment variable `STAMPBOOK_NOW` (`YYYY-MM-DDTHH:MM:SS`) to replace the system clock; an invalid value is a usage error.

## Database

The path is the global `--db PATH` option (before the command), else the environment variable `STAMPBOOK_DB`, else `./stampbook.db`. The file is created on first use with `PRAGMA user_version = 1` and one table `entries`. A database with a newer user_version is rejected.

## Exit codes

- 0: success
- 1: domain error (already running, nothing is running, clock before start, newer database)
- 2: usage error (invalid project name, note, date, clock, or command line)

Errors are printed to stderr as `stampbook: <message>`, without a traceback.

## Development

In a virtual environment:

    pip install -e . pytest ruff
    python -m pytest -q
    python -m ruff check .

## License

MIT, see [LICENSE](LICENSE).

---

Built with BAKED, an open-source coding agent (bench loop round 6, BAKED 41c4bca).
