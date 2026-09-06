# Shared Household Chores Tool

A Django app for tracking household chores. Most chore apps answer "whose turn
is it"; this one also answers "was it actually done", by requiring a photo on
completion and approval from another member of the household before the work
counts.

Chores are scheduled onto a calendar and assigned automatically, with a
one-line explanation of why each person got each chore. Approved work builds a
per-person score that resets monthly, and every correction — a rejection, an
effort override, a reassignment — is added to an append-only history rather
than overwriting what came before.

Full scope, including what is deliberately excluded, is in
[_docs/plan.md](_docs/plan.md).

## MVP scope

The first milestone is deliberately narrower than the full design. Chores are
scheduled, assigned and marked done; the approval loop is deferred and the
completion photo is optional, because a one-person household has nobody to
review the work. Scoring is unaffected — effort values are fixed on the chore
rather than self-reported, so marking your own chore done cannot inflate a
score. [_docs/plan.md](_docs/plan.md) records the deviation in full.

## Current state

Scaffolding only. **No features are implemented yet** — running the app serves
a placeholder page, not a working chore tracker.

What exists today:

- Django project (`config`) and a single domain app (`chores`)
- A custom user model, in place from the first migration
- Authentication wired up via django-allauth
- Environment-driven settings, SQLite by default
- pytest and ruff configured, with one smoke test

Work is tracked as [GitHub issues](../../issues), grouped into phase
[milestones](../../milestones). The same list, with progress, is in
[_docs/backlog.md](_docs/backlog.md).

The next task is issue #2, Household and membership.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

No database server is needed yet; the project uses SQLite.

## Running it

Install dependencies:

```bash
uv sync
```

Create your environment file:

```bash
cp .env.example .env
```

This step is required, not optional. `DEBUG` defaults to `False`, and Django
refuses to start with `DEBUG=False` and an empty `ALLOWED_HOSTS` — the error
names `ALLOWED_HOSTS` rather than the missing `.env`, so it is easy to
misdiagnose.

Apply migrations:

```bash
uv run python manage.py migrate
```

Start the server:

```bash
uv run python manage.py runserver
```

The app is then at http://127.0.0.1:8000/, currently showing the placeholder
page. To look at the admin, create a superuser first:

```bash
uv run python manage.py createsuperuser
```

The admin is at http://127.0.0.1:8000/admin/. Only users are registered so
far; the domain models arrive with issue #13.

## Tests and linting

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run ruff format .
```

## Documentation

- [_docs/plan.md](_docs/plan.md) — scope, design decisions, and deliberate
  exclusions
- [_docs/backlog.md](_docs/backlog.md) — the ordered task list, with progress
- [_docs/process.md](_docs/process.md) — how work is organized, and the roles
- [_docs/team/pm.md](_docs/team/pm.md) — the product manager role, which grooms
  a task before it is implemented
- [_docs/task-template.md](_docs/task-template.md) — the shape a groomed issue
  takes
- [AGENTS.md](AGENTS.md) — instructions for coding agents. `CLAUDE.md` imports
  it so Claude Code reads the same file.

## Notes

SQLite is the default and is fine for development. The project moves to
Postgres when it is deployed, because the web server and the scheduler loop run
as separate processes writing concurrently.

Uploaded photos are stored on local disk during development and are not
committed. They move to object storage at the same time as Postgres.
