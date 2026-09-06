# Shared Household Chores Tool

A Django app for tracking household chores. Most chore apps answer "whose turn
is it"; this one also answers "was it actually done", by requiring a photo on
completion and approval from another member of the household before the work
counts.

Chores are scheduled onto a calendar and assigned automatically, with a
one-line explanation of why each person got each chore.

## Status

Early. The project scaffold is in place; feature work has not started. See
[_docs/backlog.md](_docs/backlog.md) for the task list and progress.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## Getting started

Install dependencies:

```bash
uv sync
```

Copy the environment template and adjust if needed:

```bash
cp .env.example .env
```

This step is required. `DEBUG` defaults to `False`, and Django refuses to start
with `DEBUG=False` and an empty `ALLOWED_HOSTS` — the resulting error mentions
`ALLOWED_HOSTS` rather than the missing file.

Apply migrations and start the server:

```bash
uv run python manage.py migrate
```

```bash
uv run python manage.py runserver
```

The app is then at http://127.0.0.1:8000/.

## Running tests

```bash
uv run pytest
```

Linting and formatting use ruff:

```bash
uv run ruff check .
```

## Documentation

- [_docs/plan.md](_docs/plan.md) — scope, design decisions, and what is
  deliberately excluded
- [_docs/backlog.md](_docs/backlog.md) — ordered task list with progress
- [_docs/process.md](_docs/process.md) — how work is organized
- [AGENTS.md](AGENTS.md) — instructions for coding agents

## Notes

The database is SQLite by default, which is fine for local development. Set
`DATABASE_URL` to use Postgres.

Uploaded photos are stored on local disk during development and are not
committed.
