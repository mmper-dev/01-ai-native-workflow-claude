# Shared Household Chores Tool

Django app for tracking household chores with photo-verified completion and
peer approval. Scope is in `_docs/plan.md`; the ordered task list is in
`_docs/backlog.md`. Read the plan before adding features — several apparent
gaps are deliberate exclusions, listed at the end of both documents.

# Commands

- `uv sync` - install dependencies
- `uv run python manage.py runserver` - start development server
- `uv run pytest` - run tests

# Rules

- Use `uv` for Python dependency management.
- Dependencies are defined in `pyproject.toml`.
- Ask before adding new dependencies.
- Do not modify database migrations manually.
- Run tests after making changes.

# Documents

- `_docs/process.md` - how work is organized
- Before writing tests, read `_docs/testing-guidelines.md`
- For anything touching the UI, read `_docs/design-system.md`

Some of these are not written yet. If one is missing, carry on without it and
use your judgement — a missing file is expected, not an error worth stopping
or complaining about.

# Setup

Copy `.env.example` to `.env` before running anything. `DEBUG` defaults to
`False`, and Django refuses to start with `DEBUG=False` and an empty
`ALLOWED_HOSTS` — the resulting error names `ALLOWED_HOSTS` rather than the
missing file, so it is easy to misdiagnose. `.env` is gitignored and holds a
generated `SECRET_KEY`; never commit it.

# Layout

- `config/` - project settings, root URLs, WSGI/ASGI
- `chores/` - the single domain app, including the custom `User` model
- `chores/tests/` - pytest tests, one file per area
- `_docs/` - plan and backlog
- `templates/`, `static/` - project-level template and asset roots

# Conventions

- Database is SQLite by default. Set `DATABASE_URL` to use Postgres, which the
  backlog's "Move to Postgres and deploy" task introduces once the web server
  and the scheduler loop run as separate processes writing concurrently.
- The backend runs as two processes in production: the web server, and a
  scheduler loop that generates occurrences and marks them overdue. Never run
  the loop inside a web worker — it would be duplicated once per worker.
- `ruff` handles both linting and formatting: `uv run ruff check .` and
  `uv run ruff format .`. Migrations are excluded from both.
- Tests use `--reuse-db`. Pass `--create-db` after a schema change if a test
  database looks stale.
- Frontend is Django templates with HTMX and Alpine from a CDN. There is no
  frontend build step, and adding one is a decision worth raising first.
- Time-dependent logic must accept an injected clock rather than reading the
  current time directly, so scheduling and monthly resets stay testable.

# Domain rules that are easy to get wrong

- **Effort values are read from the occurrence, never the definition.** Each
  `ChoreOccurrence` stores its own copy of estimated duration and difficulty,
  taken when it was created. Editing a definition must affect future
  occurrences only — otherwise an override silently rewrites past scores.
- **The completion photo is required at the model level**, not just on the
  form. It is the entire verification mechanism.
- **The feed is append-only.** Corrections — effort overrides, rejections,
  reassignments — add entries and record who acted. Never update or delete an
  existing entry.
- **Overdue is a flag, not a state.** An overdue occurrence is still assigned
  and still owed, and nothing may reassign it automatically. Moving
  responsibility between people requires a person to act.
- **Skills and availability are eligibility constraints, not weights.** Someone
  lacking a required skill is excluded from assignment regardless of how long
  since their last chore.
- **Approval is the only route to credit**, and on stretch chores the only
  route to gaining a skill. A rejected attempt grants nothing but is kept.
