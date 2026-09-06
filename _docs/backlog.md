# Backlog — Django build

Derived from [plan.md](plan.md). Milestones follow the plan's build order.
Milestones 1–3 form a usable tool on their own; everything after is additive.

Each task lists a **Done when** so it can be closed without re-reading the plan.

---

## M0 — Scaffold ✅

| # | Task | Done when |
|---|---|---|
| 0.1 | Django project `config` + app `chores`, uv-managed | `manage.py check` clean |
| 0.2 | Custom `User` from migration zero, env-driven settings, allauth wired | Smoke test passes |

---

## M1 — Definitions, occurrences, people, photo logging

The first demonstrable slice: a household can add chores and log them with photos.

| # | Task | Done when |
|---|---|---|
| 1.1 | `Household` + `Membership` models. Membership carries a roles *set*, not a single admin flag — the plan leaves "how the admin is chosen" open, and a set costs nothing now. | A user can belong to a household with one or more roles |
| 1.2 | `ChoreDefinition`: name, assignment mode (rotate/assign/claim), recurrence (interval or one-off), `estimated_minutes`, `difficulty`. Skills deferred to M4. | A definition can be created; all three modes are valid choices |
| 1.3 | `ChoreOccurrence` with **snapshot** `estimated_minutes` / `difficulty` copied from the definition at creation, plus `due_at`, `assignee`, `state`. | Editing a definition leaves existing occurrences' effort values untouched — covered by a test |
| 1.4 | Occurrence state field + guarded transitions (pending → logged → approved / rejected → pending). `overdue_at` is a **separate nullable timestamp**, not a state. | Illegal transitions raise; an overdue occurrence is still pending and still assigned |
| 1.5 | Occurrence materializer: given a definition and a horizon, create missing future occurrences idempotently. Called by hand for now, scheduled in M5. | Running it twice produces no duplicates |
| 1.6 | `CompletionLog` with a **required** `ImageField` and the chosen approver FK. | A completion cannot be saved without a photo — model-level, not just form-level |
| 1.7 | Views: occurrence list for my household, occurrence detail, log-completion form with photo upload. HTMX + Alpine from CDN, no build step. | A logged-in member can see their chores and log one with a photo |
| 1.8 | Register everything in Django admin — this is the plan's "admin powers" surface for now. | Admin can create definitions and view occurrences |

**Risk:** 1.3 is the one that is expensive to retrofit. If the snapshot fields are
skipped "for now", every score written before the fix is wrong and unrecoverable.

---

## M2 — Approval, rejection, feed

| # | Task | Done when |
|---|---|---|
| 2.1 | `FeedEntry`: `actor`, `verb`, `occurrence`, `payload` (JSON), `created_at`. Append-only — no update or delete path in application code. | Entries can be created and read, never modified |
| 2.2 | Enforce append-only at the DB level once Postgres is in (`django-pgtrigger`). Until then, override `save()` to reject changes to an existing row. | Modifying a saved `FeedEntry` raises |
| 2.3 | Approve action: approver confirms → occurrence approved, feed entry written. | Approval is the only route to approved |
| 2.4 | Reject action with a **required written reason**. The rejected attempt is kept, not deleted; the occurrence returns to the same assignee. | Rejected `CompletionLog` rows still exist and are visible on the occurrence |
| 2.5 | Rejection counter. At 2 rejections, flag for admin resolution and stop the redo loop. | A third rejection is blocked; the occurrence appears in an admin queue |
| 2.6 | Public feed view — household-wide, chronological, showing who acted and when. | Approvals, rejections and overrides each appear as separate entries |
| 2.7 | Overdue sweep as a management command: set `overdue_at`, notify the assignee by email (console backend). **Never reassigns.** | Running it twice does not re-notify |

**On 2.4:** the plan accepts that self-chosen approvers can rubber-stamp, and
mitigates it with feed visibility rather than mechanism. Do not add approver
restrictions here — they are explicitly out of scope.

---

## M3 — Scoring

| # | Task | Done when |
|---|---|---|
| 3.1 | Score = sum of `estimated_minutes × difficulty` over **approved** occurrences in the current period, read from the occurrence snapshot. | Never reads the definition; a test proves an edited definition cannot move a past score |
| 3.2 | Monthly period boundary and reset that starts a new period. The feed is untouched. | Scores zero at the boundary; every feed entry survives |
| 3.3 | Scoreboard view — per-person, current period. | Members see individual figures, per the plan's deliberate choice |
| 3.4 | Admin effort override: writes a feed entry recording who changed what, then recomputes. | The override is visible in the feed and the score changes |

**M1–M3 is the shippable product.** Stop here if time runs short.

---

## M4 — Skills and calendars (data models only)

| # | Task | Done when |
|---|---|---|
| 4.1 | `Skill` model, `ChoreDefinition.required_skills` M2M, `Membership.skills` M2M. | Definitions and members can both hold skills |
| 4.2 | `Availability` on `Membership` — enough to answer "is X free at time T". | A single query answers the availability question |
| 4.3 | `Membership.stretch_learning_opt_in` boolean. | Toggleable per member, per household |

No behaviour yet — the M5 scheduler is the first consumer.

---

## M5 — Scheduler (the largest piece)

| # | Task | Done when |
|---|---|---|
| 5.1 | Pure-Python `assign(occurrence, candidates) -> Assignment` in `chores/scheduling.py` with **no Django imports**. Returns the chosen person, a one-line reason, and excluded candidates with causes. | Unit-testable with plain objects; runs in milliseconds |
| 5.2 | Eligibility filter: skills and availability are **hard constraints, not weights**. A member lacking a required skill is excluded regardless of rotation position. | A test asserts an unskilled member is never chosen, even at the front of the rotation |
| 5.3 | Rotation ordering by lowest recent effort among eligible candidates. | Reproducible under a fixed clock (`time-machine`) |
| 5.4 | Deferral: when nobody is eligible, push the due date and flag it. **Surface the stuck chore in the UI** — the plan is explicit that it must not defer silently. | A chore nobody qualifies for appears in a needs-attention list, not just a log line |
| 5.5 | Persist the assignment reason on the occurrence and display it. | Every assignment shows its one-line explanation |
| 5.6 | Run the materializer and overdue sweep on a schedule. Add the queue here, not earlier — Procrastinate (Postgres-backed) unless something else pulls in Redis. | Occurrences appear and go overdue without manual commands |

**5.5 is not cosmetic.** The plan says the scheduler is otherwise invisible and the
explanation is what makes it demonstrable. Ship it with 5.1–5.3, not after.

---

## M6 — Stretch-learning

Depends on M5 and M2.

| # | Task | Done when |
|---|---|---|
| 6.1 | When no eligible candidate exists, offer the chore to opted-in members who lack the skill; mark the occurrence as a stretch. | Stretch assignment happens only after normal eligibility fails |
| 6.2 | On **approval** of a stretch occurrence, add the skill to the assignee's skill set and write a feed entry. | Rejection grants nothing; approval is the only route |

---

## M7 — AI estimation (optional)

| # | Task | Done when |
|---|---|---|
| 7.1 | `EffortSuggestion` row written by a background task calling Claude with structured output (`{minutes, difficulty, rationale}`). | A chore is fully creatable and usable before any suggestion arrives |
| 7.2 | UI shows the suggestion as a proposal requiring confirmation; manual entry always works. | Removing the API key breaks nothing — covered by a test with the call stubbed to fail |

**7.2 is the acceptance criterion for the whole milestone.** The plan names AI
estimation as the safest thing to defer precisely because nothing may depend on it.

---

## Explicitly not in this backlog

Out of scope per the plan, listed so they do not creep back in: majority voting on
approvals, escalation chains, restrictions on approver choice, self-reported actual
time, chore dependencies or blocked-by relationships, and swaps between members.

## Open question, blocking nothing yet

How the admin is chosen, and whether there can be more than one. Task 1.1 models
roles as a set so this can be answered late without a data migration on real data.
