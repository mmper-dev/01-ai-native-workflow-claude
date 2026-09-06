# Backlog — Django build

Derived from [plan.md](plan.md). Tasks are ordered so there is always something
demonstrable, but each one is written to be handed to someone who has read only
the plan and this task. Where a task assumes an earlier one, its description
says so and names the model involved rather than pointing at a task number.

Each task is sized for a single session.

**Tasks 1–19 form a usable tool on their own.** Everything from 20 onward adds
the scheduler and the features that depend on it.

---

## 1. Empty project with a passing test
Goal: A Django project that boots, runs its test suite green, and is ready for models.
Description: Create the Django project and a single app for the chores domain, managed with uv. Add a custom user model in that app from the very first migration — swapping it in later is a painful retrofit. Finish with one smoke test that hits a placeholder view and asserts a 200, so the suite has something real to run. **Status: done.**

## 2. Household and membership
Goal: People can belong to a household, with roles.
Description: Add a `Household` model and a `Membership` model joining users to households. Membership carries a set of roles rather than a single `is_admin` boolean, because the plan leaves open how the admin is chosen and whether there can be more than one — a set costs nothing now and avoids a data migration later. Skills and availability are not part of this task.

## 3. Chore definition model
Goal: A household can describe a reusable piece of work.
Description: Add a `ChoreDefinition` belonging to a household, with a name, an assignment mode (rotate, assign, or claim), a recurrence that is either a fixed interval or one-off, an estimated duration in minutes, and a difficulty weight. Skill requirements are a later task and should be left out. Anyone in the household can create one, so do not gate creation on a role.

## 4. Chore occurrence with frozen effort values
Goal: Each due instance of a chore is a separate record that keeps its own effort values.
Description: Add a `ChoreOccurrence` pointing at a `ChoreDefinition`, with its own due date, assignee, and state, plus **copies** of the estimated duration and difficulty taken at creation time. The copies are the point of this task: the plan requires that editing a definition affects future occurrences only, so completed work keeps the values it was scored under. Include a test proving that editing a definition leaves an existing occurrence's effort values untouched.

## 5. Occurrence lifecycle and the overdue flag
Goal: An occurrence moves through its states safely, and overdue is a flag rather than a state.
Description: Add guarded transitions to `ChoreOccurrence` covering pending → logged → approved or rejected, with rejection returning it to pending. Model overdue as a separate nullable timestamp alongside the state, not as a state of its own — the plan is explicit that an overdue chore is still assigned and still owed. Illegal transitions should raise rather than silently no-op.

## 6. Generating occurrences from a definition
Goal: Future occurrences appear automatically from a definition's recurrence rule.
Description: Write a function that takes a `ChoreDefinition` and a time horizon and creates any missing `ChoreOccurrence` rows up to that horizon. It must be idempotent — running it twice produces no duplicates — because it will later run on a schedule. Expose it as a management command for now; wiring it to a background scheduler is a separate task.

## 7. Completion log with a required photo
Goal: Completing a chore requires a photo and a chosen approver.
Description: Add a `CompletionLog` attached to a `ChoreOccurrence`, holding an image field and a foreign key to the household member the assignee picked as approver. The photo is required at the model level, not merely on the form — the plan treats it as the entire verification mechanism. Store uploads on local disk for now; swapping in remote object storage is a deployment concern, not this task.

## 8. Chore list and detail views
Goal: A logged-in member can see the chores in their household.
Description: Add a list view of `ChoreOccurrence` rows for the current user's household, and a detail view for a single occurrence showing its due date, assignee, effort values, and current state. Use Django templates with HTMX and Alpine loaded from a CDN, so there is no frontend build step. Read-only — actions are separate tasks.

## 9. Logging a completion
Goal: An assignee can complete a chore by uploading a photo and naming an approver.
Description: Add a form and view that creates a `CompletionLog` against an occurrence and moves that occurrence into its logged state. The approver dropdown lists every other member of the household; the plan explicitly rules out restricting who may be chosen, so add no filtering beyond excluding the assignee. Reject a submission with no photo.

## 10. Django admin registration
Goal: An admin can inspect and edit the domain through Django's built-in admin.
Description: Register households, memberships, chore definitions, occurrences, and completion logs in the Django admin with sensible list displays and filters. This is the plan's admin surface for the early milestones and saves building bespoke screens. Purpose-built admin actions like effort overrides are separate tasks.

## 11. Append-only feed model
Goal: There is a record of who did what, that cannot be rewritten.
Description: Add a `FeedEntry` with an actor, a verb, a link to the occurrence, a JSON payload for details, and a creation timestamp. Nothing in the application may update or delete an entry — corrections are new entries, per the plan. Enforce this in the model's save path for now, and add a database-level trigger once the project is on Postgres.

## 12. Approving a completion
Goal: A chosen approver can confirm a logged chore, which is the only route to credit.
Description: Add an approve action available to the approver named on a `CompletionLog`. On approval the occurrence becomes approved and a `FeedEntry` is written recording who approved and when. No other path may set an occurrence to approved.

## 13. Rejecting a completion
Goal: An approver can reject work, with a written reason, without erasing the attempt.
Description: Add a reject action requiring a non-empty written reason. The rejected `CompletionLog` is kept rather than deleted, and the occurrence returns to the same assignee to redo — the plan forbids silently moving responsibility to someone else. Write a `FeedEntry` capturing the rejection and its reason.

## 14. Rejection limit and admin resolution
Goal: A chore that has been rejected twice stops looping and lands with the admin.
Description: Count rejections per occurrence and, once there are two, block further rejections and flag the occurrence for admin resolution. Add a view listing flagged occurrences and an action letting an admin resolve one. The plan does not specify what resolution means beyond the admin deciding, so allow both approving and cancelling, and record either as a `FeedEntry`.

## 15. Public feed view
Goal: The household can see the history of what happened.
Description: Add a chronological, household-scoped view of `FeedEntry` rows showing who acted, what they did, and when. This is what makes approval patterns visible, which the plan relies on as its mitigation for approvers rubber-stamping. Include approvals, rejections, effort overrides, and reassignments in the same stream.

## 16. Overdue sweep and notification
Goal: An occurrence whose due time has passed is flagged and its assignee is told.
Description: Write a management command that finds pending occurrences past their due time, sets the overdue timestamp, and emails the assignee using Django's console email backend. It must never reassign the chore — the plan requires that moving responsibility takes a human action. Running it twice must not send duplicate notifications.

## 17. Score computation
Goal: Each person has a score reflecting the approved work they have done.
Description: Compute a per-person score as the sum of estimated duration multiplied by difficulty across their approved occurrences in the current period, reading the effort values **stored on the occurrence** rather than on the definition. This is what stops a later edit from rewriting past scores. Include a test that edits a definition and asserts an already-approved occurrence's contribution does not move.

## 18. Monthly reset
Goal: Scores start fresh each month while the history remains.
Description: Add the notion of a scoring period with a monthly boundary, and make score computation consider only the current period. The feed is untouched by the reset — the plan keeps history permanent and resets only the numbers. Make the boundary testable with a controllable clock rather than reading the real date directly.

## 19. Scoreboard view
Goal: Members can see how the current month is going.
Description: Add a view listing each household member with their score for the current period. Per-person figures are a deliberate choice in the plan, not an oversight, so do not aggregate them into a household total. Link through to the feed so a surprising number can be understood in context.

## 20. Admin effort override
Goal: An admin can correct a chore's effort values, visibly.
Description: Add an admin action that changes the estimated duration or difficulty and writes a `FeedEntry` recording who changed what, from which values to which. Scores recompute afterwards. The plan accepts that this lets an admin move scores, and relies on the append-only history to make it visible rather than preventing it.

## 21. Skills
Goal: Chores can require skills, and people can have them.
Description: Add a `Skill` model, a many-to-many from chore definitions for required skills, and a many-to-many from memberships for the skills a person holds. Data only — nothing consumes these yet, and assignment behaviour is a later task. Make skills household-scoped rather than global.

## 22. Availability
Goal: The system can answer whether a member is free at a given time.
Description: Add an availability calendar to membership, enough to answer "is this person free at this time" in a single query. Keep the representation as simple as the question allows; recurring weekly windows are likely sufficient. Data only — no assignment logic in this task.

## 23. Stretch-learning opt-in
Goal: A member can volunteer to be given chores they are not yet qualified for.
Description: Add a boolean opt-in flag to membership, editable by the member themselves. Nothing reads it yet. It exists so that the assignment rules, when built, have a real signal to act on rather than guessing.

## 24. Eligibility filtering
Goal: Given a chore and a set of candidates, determine who is actually eligible.
Description: Write a pure-Python function, with no Django imports, that filters candidates by required skills and availability. Both are **hard constraints, not weights** — someone lacking a required skill is excluded no matter how long since their last chore, which is what makes stretch-learning a real decision rather than a tiebreak. Return the excluded candidates with the reason each was excluded.

## 25. Rotation ordering
Goal: Among eligible candidates, pick the one with the lowest recent effort.
Description: Extend the assignment logic to order eligible candidates by their recent effort total and choose the lowest. Keep it in the same pure-Python module so it stays testable with plain objects and no database. Use an injected clock rather than reading the current time directly, so rotation is reproducible in tests.

## 26. Assignment explanations
Goal: Every assignment shows a one-line reason.
Description: Have the assignment logic return a human-readable reason alongside the chosen person — for example "Assigned to Alex — available, and lowest recent effort" — then persist it on the occurrence and display it in the UI. The plan calls this out specifically: the scheduler is the largest piece of the build and otherwise invisible, and the explanation is what makes it demonstrable. Ship this with the assignment logic, not after it.

## 27. Deferral when nobody qualifies
Goal: A chore nobody can do is pushed back and made visible.
Description: When no candidate is eligible, move the occurrence's due date and flag it. Add a "needs attention" list surfacing these, because the plan warns that such a chore will otherwise keep deferring forever with nobody noticing. A log line is not sufficient — it has to appear in the UI.

## 28. Wiring assignment into occurrence creation
Goal: Newly generated occurrences arrive with an assignee already chosen.
Description: Connect the assignment logic to occurrence generation so that each new occurrence in rotate mode gets an assignee and a stored reason. Respect the definition's assignment mode: assign mode takes a fixed person, and claim mode leaves the assignee empty until someone takes it. This is the task where the pure functions meet the database.

## 29. Running the scheduler on a timer
Goal: Occurrences appear and go overdue without anyone running a command.
Description: Introduce a background job runner and schedule the occurrence generator and the overdue sweep. Prefer a Postgres-backed queue such as Procrastinate over Celery unless something else in the project already needs Redis, since it means one fewer service to run. This is the first task that requires Postgres rather than SQLite.

## 30. Stretch assignment
Goal: An opted-in member can be given a chore they lack the skill for.
Description: When no eligible candidate exists, offer the chore to members who have opted into stretch-learning but lack the required skill, and mark the resulting occurrence as a stretch. This must be attempted only after normal eligibility has failed, so that stretch assignment stays an exception rather than a shortcut. If nobody has opted in, fall back to deferring.

## 31. Granting skills through approval
Goal: Completing a stretch chore successfully teaches the skill.
Description: When a stretch occurrence is approved, add the required skill to the assignee's skill set and write a `FeedEntry` recording it. Approval is the only route — a rejected stretch attempt grants nothing. This closes the loop the plan describes, where the approval mechanism and the skill system feed each other.

## 32. AI effort estimation
Goal: Adding a chore can suggest a duration and difficulty, without ever blocking.
Description: Add a suggestion record written by a background job that asks Claude for a structured estimate of duration, difficulty, and a short rationale for a chore description. The chore must be fully creatable and usable before any suggestion arrives, since the plan names this the safest thing to defer and requires that manual entry always works. Never call the model in the request path.

## 33. Showing suggestions safely
Goal: Suggestions appear as proposals a human confirms, and failure changes nothing.
Description: Display any AI suggestion on the chore form as a pre-fill the user can accept, edit, or ignore, with household agreement confirming it and the admin able to override. Include a test that stubs the model call to fail and asserts a chore can still be created and used normally. That test is the acceptance criterion for this work — nothing in the tool may depend on the AI path.

---

## Out of scope

Listed so they do not creep back in mid-build: majority voting on approvals,
escalation chains, restrictions on who the assignee may pick as approver,
self-reported actual time, chore dependencies or blocked-by relationships, and
swaps between members.

## Open question

How the admin is chosen, and whether there can be more than one. Task 2 models
roles as a set so this can be answered late without migrating real data.
