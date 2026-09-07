# Backlog — Django build

Derived from [plan.md](plan.md). Each task is sized for a single session and
written to be handed to someone who has read only the plan and that task.

Every task is a GitHub issue, and the numbers below are issue numbers. Tick a
box here in the same change that closes the issue, so status cannot drift from
the code.

Issues carry an `mvp` or `post-mvp` label, so the MVP can be filtered out of
the tracker without reading milestones.

## MVP scope

The MVP is Phase 1: chores are scheduled onto a calendar, assigned
automatically with a visible reason, shown as overdue when missed, and marked
done by the assignee.

Two things from plan.md are **not** in it:

- **The approval loop is deferred.** A one-person household has nobody to
  approve anything, which makes approval impossible rather than merely
  optional. The work is kept in the Deferred section below rather than dropped.
- **The completion photo is optional**, not required. Without an approver there
  is nobody to show it to, but the field stays so a household that wants
  evidence can attach it.

This means the MVP answers "whose turn is it" but not "was it actually done",
which plan.md names as the differentiator. That is a deliberate trade to get
something working, not an oversight. Scoring is unaffected: effort values are
fixed on the chore rather than self-reported, so marking your own chore done
cannot inflate your score.

---

## Progress

**Phase 1 — MVP**

- [x] #1 Empty project with a passing test
- [ ] #2 Household and membership
- [ ] #3 Chore definition model
- [ ] #35 Preloaded chore library
- [ ] #4 Chore occurrence with frozen effort values
- [ ] #5 Occurrence lifecycle and the overdue flag
- [ ] #6 Generating occurrences from a definition
- [ ] #7 Round-robin assignment with a reason
- [ ] #8 Base templates and authentication pages
- [ ] #9 Chore calendar and detail views
- [ ] #10 Marking a chore done, with an optional photo
- [ ] #11 Claiming an unassigned chore
- [ ] #12 Scheduler loop
- [ ] #13 Django admin registration

**Phase 2 — History and notifications**

- [ ] #14 Append-only feed model
- [ ] #19 Public feed view
- [ ] #20 Overdue notification

**Phase 3 — Scoring**

- [ ] #21 Score computation with monthly periods
- [ ] #22 Scoreboard view
- [ ] #23 Admin effort override

**Phase 4 — Real scheduling**

- [ ] #24 Skills
- [ ] #25 Availability
- [ ] #26 Stretch-learning opt-in
- [ ] #27 Eligibility filtering
- [ ] #28 Effort-based rotation
- [ ] #29 Deferral when nobody qualifies

**Phase 5 — Stretch learning**

- [ ] #30 Stretch assignment
- [ ] #31 Granting skills on completion of a stretch chore

**Phase 6 — Deployment**

- [ ] #32 Move to Postgres and deploy

**Phase 7 — AI estimation**

- [ ] #33 AI effort estimation
- [ ] #34 Showing suggestions safely

**Follow-ups — post-MVP**

- [ ] #36 Removing a member without orphaning history
- [ ] #37 Every household keeps at least one admin
- [ ] #38 Pausing a chore definition
- [ ] #39 Richer recurrence rules
- [ ] #40 Re-freezing effort values on already-generated occurrences

**Deferred — Approval loop**

- [ ] #15 Choosing an approver and approving
- [ ] #16 Rejecting a completion
- [ ] #17 Rejection limit
- [ ] #18 Admin resolution of stuck chores

---

# Phase 1 — MVP

## 1. Empty project with a passing test

**Goal:** A Django project that boots, runs its test suite green, and is ready
for models.

**Description:** Create the Django project and a single app for the chores
domain, managed with uv. Add a custom user model in that app from the very
first migration — swapping it in later is a painful retrofit. Finish with one
smoke test that hits a placeholder view and asserts a 200.

---

## 2. Household and membership

**Goal:** A user can be a member of a household, and that membership can carry
one or more roles, so later work can ask "who is in this household" and "is
this person an admin".

**Description:** Add a `Household` model, with a name and a timezone, and a
`Membership` model joining users to households. Membership carries a set of
roles rather than a single `is_admin` boolean, because the plan leaves open how
the admin is chosen and whether there can be more than one. Skills and
availability are not part of this task.

**Groomed** — see [issue #2](../../../issues/2) for acceptance criteria, out of
scope, and constraints.

---

## 3. Chore definition model

**Goal:** A household can describe a reusable piece of work, with enough detail
for the scheduler to place it on a calendar and for scoring to value it.

**Description:** Add a `ChoreDefinition` belonging to a household, with a name,
a start date, an assignment mode (rotate, assign, or claim), a recurrence that
is either one-off or a fixed interval in days, an estimated duration in
minutes, and a difficulty from 1 to 5. Assign mode names a fixed member; the
other two do not. Skill requirements are a later task. Anyone in the household
can create one, so do not gate creation on a role.

**Groomed** — see [issue #3](../../../issues/3) for acceptance criteria, out of
scope, and constraints.

---

## 35. Preloaded chore library

**Goal:** A fresh install has a set of realistic chores to start from.

**Description:** Add a management command that loads a library of common
household chores into a household — dishes, bins, bathroom, vacuuming, laundry,
changing sheets and similar — each with a sensible recurrence, estimated
duration and difficulty. This makes a new install immediately usable and gives
the calendar something to show without anyone typing fifteen chores in by hand.
Loading twice must not duplicate anything.

---

## 4. Chore occurrence with frozen effort values

**Goal:** Each due instance of a chore is a separate record that keeps its own
effort values.

**Description:** Add a `ChoreOccurrence` pointing at a `ChoreDefinition`, with
its own due date, assignee, and state, plus copies of the estimated duration
and difficulty taken at creation time. The copies are the point of this task:
editing a definition must affect future occurrences only, so completed work
keeps the values it was scored under.

**Groomed** — see [issue #4](../../../issues/4) for acceptance criteria, out of
scope, and constraints.

---

## 5. Occurrence lifecycle and the overdue flag

**Goal:** An occurrence moves through its states safely, and overdue is a flag
rather than a state.

**Description:** Add guarded transitions to `ChoreOccurrence` covering pending
→ done. Model overdue as a separate nullable timestamp alongside the state,
because an overdue chore is still assigned and still owed. Illegal transitions
should raise rather than silently no-op. The approval states are deferred.

---

## 6. Generating occurrences from a definition

**Goal:** Future occurrences appear automatically from a definition's
recurrence rule.

**Description:** Write a function that takes a `ChoreDefinition` and a time
horizon and creates any missing `ChoreOccurrence` rows up to that horizon. It
must be idempotent, because a background loop will call it repeatedly. Expose
it as a management command so it can be run by hand and tested in isolation.

---

## 7. Round-robin assignment with a reason

**Goal:** Generated occurrences arrive with someone assigned and a one-line
explanation.

**Description:** Assign each new occurrence in rotate mode to the household
member who least recently did one, and store a human-readable reason alongside
the assignee. Skills and availability are not considered yet; a later task
replaces this rule with real eligibility logic, and the stored reason is what
makes that upgrade visible. Assign mode takes a fixed person and claim mode
leaves the assignee empty.

---

## 8. Base templates and authentication pages

**Goal:** There is a page shell to hang every later screen on, and a way to log
in.

**Description:** Add a base template with navigation and message display, and
the login, logout, and signup templates that django-allauth expects. Load HTMX
and Alpine from a CDN here so no later task needs to decide that. This is its
own task because it is invisible groundwork that would otherwise be smuggled
into the first screen someone builds.

---

## 9. Chore calendar and detail views

**Goal:** A member can see what is due, who has it, and what is overdue.

**Description:** Add a date-ordered view of upcoming `ChoreOccurrence` rows for
the current user's household, showing the assignee, the due date, the stored
assignment reason, and a clear marker for anything overdue. Add a detail view
for a single occurrence. This is the screen that carries the demo, so it is
worth more care than the ones that follow.

---

## 10. Marking a chore done, with an optional photo

**Goal:** An assignee can mark a chore done, attaching a photo if they want to.

**Description:** Add a `CompletionLog` attached to an occurrence with an
optional image field, plus the form and view that create it and move the
occurrence into its done state. The photo is optional rather than required: a
one-person household has nobody to show it to, and approval is deferred. Keep
the field so evidence is possible for households that want it.

---

## 11. Claiming an unassigned chore

**Goal:** A chore in claim mode can be picked up by whoever wants it.

**Description:** Add an action letting any member of the household take an
occurrence that has no assignee, setting themselves as the assignee. This
applies to chore definitions whose assignment mode is claim, which produce
occurrences with the assignee left empty. Once claimed, the chore behaves like
any other assigned occurrence.

---

## 12. Scheduler loop

**Goal:** The backend keeps the calendar current on its own, without anyone
running a command.

**Description:** Add a management command that loops on an interval, calling
the occurrence generator and marking passed-due occurrences as overdue. Run it
as a separate process from the web server so it is never duplicated across web
workers, and make the interval and a single-pass mode configurable so it can be
tested without waiting. Log each pass, because a loop that dies silently is the
main failure mode.

---

## 13. Django admin registration

**Goal:** An admin can inspect and edit the domain through Django's built-in
admin.

**Description:** Register households, memberships, chore definitions,
occurrences, and completion logs with sensible list displays and filters. This
is deliberately the only way to create a household or add a member, which is
why it is worth doing properly rather than accepting the defaults. Effort
overrides and other purpose-built actions are separate tasks.

---

# Phase 2 — History and notifications

## 14. Append-only feed model

**Goal:** There is a record of who did what, that cannot be rewritten.

**Description:** Add a `FeedEntry` with an actor, a verb, a link to the
occurrence, a JSON payload, and a creation timestamp. Nothing may update or
delete an entry — corrections are new entries. Enforce this with a database
trigger that aborts updates and deletes, which both SQLite and Postgres
support. In the MVP the verbs are completions, effort overrides and
reassignments.

---

## 19. Public feed view

**Goal:** The household can see the history of what happened.

**Description:** Add a chronological, household-scoped view of `FeedEntry` rows
showing who acted, what they did, and when. Include completions, effort
overrides and reassignments in the same stream. This is the append-only history
the plan requires: corrections add entries rather than replacing them.

---

## 20. Overdue notification

**Goal:** The assignee is told when a chore of theirs goes overdue.

**Description:** Have the background loop email the assignee when it marks an
occurrence overdue, using Django's console email backend for now. Stamp a
notified timestamp so a chore that stays overdue is not emailed on every pass.
The loop must never reassign the chore.

---

# Phase 3 — Scoring

## 21. Score computation with monthly periods

**Goal:** Each person has a score for the current month, reflecting completed
work.

**Description:** Add the notion of a monthly scoring period, and compute a
per-person score as the sum of estimated duration multiplied by difficulty
across their completed occurrences within the current period. Read the effort
values stored on the occurrence rather than on the definition — this is what
stops a later edit from rewriting past scores, and why self-marking cannot
inflate a score. Make the period boundary testable with a controllable clock.

---

## 22. Scoreboard view

**Goal:** Members can see how the current month is going.

**Description:** Add a view listing each household member with their score for
the current period. Per-person figures are a deliberate choice in the plan, not
an oversight, so do not aggregate them into a household total. Link through to
the feed so a surprising number can be understood in context.

---

## 23. Admin effort override

**Goal:** An admin can correct a chore's effort values, visibly.

**Description:** Add an admin action that changes the estimated duration or
difficulty and writes a `FeedEntry` recording who changed what, from which
values to which. Scores recompute afterwards. The plan accepts that this lets
an admin move scores, and relies on append-only history to make it visible
rather than preventing it.

---

# Phase 4 — Real scheduling

## 24. Skills

**Goal:** Chores can require skills, and people can have them.

**Description:** Add a `Skill` model, a many-to-many from chore definitions for
required skills, and a many-to-many from memberships for the skills a person
holds. Data only — nothing consumes these yet. Make skills household-scoped
rather than global.

---

## 25. Availability

**Goal:** The system can answer whether a member is free at a given time.

**Description:** Add an availability calendar to membership, enough to answer
"is this person free at this time" in a single query. Keep the representation
as simple as the question allows; recurring weekly windows are likely
sufficient. Data only — no assignment logic in this task.

---

## 26. Stretch-learning opt-in

**Goal:** A member can volunteer to be given chores they are not yet qualified
for.

**Description:** Add a boolean opt-in flag to membership, editable by the
member themselves. Nothing reads it yet. It exists so that the assignment
rules, when built, have a real signal to act on rather than guessing.

---

## 27. Eligibility filtering

**Goal:** Given a chore and a set of candidates, determine who is actually
eligible.

**Description:** Write a pure-Python function, with no Django imports, that
filters candidates by required skills and availability. Both are hard
constraints, not weights — someone lacking a required skill is excluded no
matter how long since their last chore. Return the excluded candidates with the
reason each was excluded.

---

## 28. Effort-based rotation

**Goal:** Assignment picks the eligible person with the lowest recent effort,
and says why.

**Description:** Replace the round-robin rule with one that orders eligible
candidates by recent effort total and chooses the lowest, keeping the stored
one-line reason. Keep the logic in the same pure-Python module so it stays
testable with plain objects, and use an injected clock so rotation is
reproducible. The reason string is not cosmetic — the scheduler is otherwise
invisible.

---

## 29. Deferral when nobody qualifies

**Goal:** A chore nobody can do is pushed back and made visible.

**Description:** When no candidate is eligible, move the occurrence's due date
and flag it. Add a "needs attention" list surfacing these, because such a chore
will otherwise keep deferring forever with nobody noticing. A log line is not
sufficient — it has to appear in the UI.

---

# Phase 5 — Stretch learning

## 30. Stretch assignment

**Goal:** An opted-in member can be given a chore they lack the skill for.

**Description:** When no eligible candidate exists, offer the chore to members
who have opted into stretch-learning but lack the required skill, and mark the
occurrence as a stretch. This must be attempted only after normal eligibility
has failed, so stretch assignment stays an exception rather than a shortcut. If
nobody has opted in, fall back to deferring.

---

## 31. Granting skills on completion of a stretch chore

**Goal:** Completing a stretch chore teaches the skill.

**Description:** When a stretch occurrence is marked done, add the required
skill to the assignee's skill set and write a `FeedEntry` recording it. With
the approval loop deferred, completion is the trigger; if approval is built
later, this moves to approval instead, since that was the plan's original
intent.

---

# Phase 6 — Deployment

## 32. Move to Postgres and deploy

**Goal:** The app runs somewhere other than a laptop, with a database that
suits two processes.

**Description:** Point the database at Postgres and run the full migration set
against a fresh database, fixing anything SQLite was quietly tolerating.
Postgres matters here because the web server and the scheduler loop are
separate processes writing concurrently. Move uploaded photos to object storage
at the same time, since a container filesystem will not keep them.

---

# Phase 7 — AI estimation

## 33. AI effort estimation

**Goal:** Adding a chore can suggest a duration and difficulty, without ever
blocking.

**Description:** Add a suggestion record written by a background job that asks
Claude for a structured estimate of duration, difficulty, and a short
rationale. The chore must be fully creatable and usable before any suggestion
arrives, since manual entry must always work. Never call the model in the
request path.

---

## 34. Showing suggestions safely

**Goal:** Suggestions appear as proposals a human confirms, and failure changes
nothing.

**Description:** Display any AI suggestion on the chore form as a pre-fill the
user can accept, edit, or ignore, with the admin able to override. Include a
test that stubs the model call to fail and asserts a chore can still be created
and used normally. That test is the acceptance criterion for this work.

---

# Follow-ups — post-MVP

Surfaced while grooming other tasks. Not part of any phase; picked up when they
start to matter.

## 36. Removing a member without orphaning history

**Goal:** A member can leave a household without destroying the record of what
they did.

**Description:** Membership uses `on_delete=PROTECT`, so a user who has done
chores cannot be deleted — correct, but it leaves no way to remove someone. Add
a way to deactivate a membership so the person stops being assigned new chores
while their completed work, feed entries and past scores stay intact.

---

## 37. Every household keeps at least one admin

**Goal:** A household cannot end up with nobody able to administer it.

**Description:** Nothing stops the last admin role being removed from a
household, which would leave effort overrides and other admin-only actions
unreachable. Add a check that prevents removing the final admin, or a rule for
who inherits it. Related to plan.md's open question about how the admin is
chosen.

---

## 38. Pausing a chore definition

**Goal:** A household can stop a chore recurring without deleting its history.

**Description:** Seasonal chores — mowing the lawn, defrosting the freezer —
should be pausable rather than deleted, because deleting a definition would take
its past occurrences and the scores attached to them with it. Add an active flag
that stops new occurrences being generated while leaving everything already
generated alone.

---

## 39. Richer recurrence rules

**Goal:** Chores can recur on patterns a fixed day interval cannot express.

**Description:** The MVP models recurrence as a fixed interval in days, which
cannot express "weekdays only", "every second Tuesday" or "the first of the
month". Add richer rules, most likely via `dateutil` rrule stored on the
definition. Deliberately deferred: a day interval covers most household chores
and needs no dependency.

---

## 40. Re-freezing effort values on already-generated occurrences

**Goal:** Editing a chore definition updates the occurrences that have been
generated ahead but not yet done.

**Description:** Task 4 freezes effort values at creation time, so an edit
today does not reach occurrences the generator already created for next week,
even though nobody has done them yet. That is the reading that cannot rewrite a
completed score, but it is not obviously what a household expects. Decide the
intended rule — most likely re-copying onto pending future occurrences and
leaving anything done or overdue alone — and write a `FeedEntry` per row
changed, since this moves scores the way task 23 does.

---

# Deferred — Approval loop

Dropped from the MVP because a one-person household has no reviewer. Kept here
rather than closed: a multi-person household may still want this, and it is
what plan.md considers the point of the tool. If it is built, the photo on
task 10 should become required again and scoring should count approved rather
than completed work.

## 15. Choosing an approver and approving

**Goal:** A completed chore is confirmed by someone the assignee picked.

**Description:** Extend the completion form to require choosing an approver
from the household, and add an approve action available to that person. On
approval the occurrence becomes approved and a `FeedEntry` records who approved
and when. The plan rules out restricting who may be chosen, so add no filtering
beyond excluding the assignee.

---

## 16. Rejecting a completion

**Goal:** An approver can reject work, with a written reason, without erasing
the attempt.

**Description:** Add a reject action requiring a non-empty written reason. The
rejected `CompletionLog` is kept rather than deleted, and the occurrence
returns to the same assignee to redo — responsibility must not move silently.
Write a `FeedEntry` capturing the rejection and its reason.

---

## 17. Rejection limit

**Goal:** A chore stops looping after it has been rejected twice.

**Description:** Count rejections per `ChoreOccurrence` and, once there are
two, block any further rejection and mark the occurrence as needing admin
resolution. The redo loop must not continue past this point.

---

## 18. Admin resolution of stuck chores

**Goal:** An admin can clear a chore that has hit the rejection limit.

**Description:** Add a view listing occurrences flagged as needing admin
resolution, and an action letting an admin resolve one. The plan says only that
the admin decides, so allow both approving and cancelling, and record either
outcome as a `FeedEntry` naming the admin who acted.

---

## Out of scope

Listed so they do not creep back in mid-build: majority voting on approvals,
escalation chains, restrictions on who the assignee may pick as approver,
self-reported actual time, chore dependencies or blocked-by relationships, and
swaps between members.

## Open question

How the admin is chosen, and whether there can be more than one. Task 2 models
roles as a set so this can be answered late without migrating real data.
