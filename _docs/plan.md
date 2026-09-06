# Shared Household Chores Tool — Scope

## Problem

Households struggle to track who actually did what. Existing chore apps
mostly answer "whose turn is it"; this tool answers both that and "was it
actually done", with a verifiable record.

## What the MVP actually builds

This document describes the design in full. The MVP being built deviates from
it in three places, recorded here so the two are not read as agreeing. The
ordered task list is in [backlog.md](backlog.md).

- **The approval loop is deferred.** Approval assumes someone other than the
  assignee is available to review. A one-person household has nobody, which
  makes approval impossible rather than optional. Marking a chore done is the
  only completion path in the MVP.
- **The completion photo is optional**, not required. Without an approver
  there is nobody to show it to. The field stays, so a household that wants
  evidence can attach one and requiring it later needs no migration.
- **Scoring counts completed rather than approved work.** This does not weaken
  it: effort values are fixed on the chore rather than self-reported at log
  time, so marking your own chore done still cannot inflate a score.

The consequence is that the MVP answers "whose turn is it" but not "was it
actually done" - the differentiator named in the Problem section above. That is
a deliberate trade to get something working, not an oversight. Everything below
still describes the intended end state.

## Core concepts

### Household
Any number of members. One admin role.

### Chore definition
Reusable description of a piece of work. Carries:

| Property | Values |
|---|---|
| Assignment mode | rotate / assign / claim |
| Recurrence | recurring (fixed interval) or one-off |
| Estimated duration | minutes |
| Difficulty | weight |
| Skill requirements | zero or more skills |

Anyone can add a chore to the shared list. Duration and difficulty are
AI-suggested, confirmed by household agreement, and overridable by the admin.

### Chore occurrence
Each due instance of a definition is a separate occurrence, holding its own
due date, assignee, effort values as they stood at the time, photo, approval
result, and history.

Editing a definition affects future occurrences only. Completed occurrences
keep the values they were scored under — otherwise an effort override could
silently rewrite past scores.

### Person
Each member has:
- a skill set (which chores they're qualified for)
- an availability calendar
- an opt-in flag for stretch-learning

## Assignment

Rotation runs through household members, filtered by skill requirements and
calendar availability.

Skills and availability are **eligibility constraints, not weights.** A member
who lacks a required skill is excluded regardless of how long it's been since
their last chore. This is what makes the stretch-learning exception below a
real decision rather than a tiebreak.

When nobody is both skilled and available:
- **Default:** the chore is pushed to another day and flagged.
- **Alternative:** if a member has opted into stretch-learning, they may be
  assigned it despite lacking the skill.

A chore that nobody qualifies for and nobody opts into will keep deferring.
Surface this in the UI rather than deferring silently.

Every assignment shows a one-line reason ("Assigned to Alex — available, and
lowest recent effort"). The scheduler is the largest piece of the build and
otherwise invisible; the explanation is what makes it demonstrable.

## Overdue

An occurrence whose due time passes without approval is marked overdue and the
assignee is notified. Overdue is a flag on a live occurrence, not a terminal
state — the chore stays assigned and the work is still owed.

Overdue never silently reassigns. Moving responsibility between people requires
someone to act.

## Completion and approval

1. Assignee completes the chore and logs it with a photo. The photo is
   required, not optional — it is the whole verification mechanism.
2. Assignee picks an approver from the household.
3. Approver confirms or rejects. Rejection carries a written reason.
4. On approval: the entry enters the public feed and scores.
5. On approval of a **stretch** chore: the skill is added to the assignee's
   skill set.
6. On rejection: back to the same person to redo. The rejected attempt is kept.
7. After 2 rejections: the admin decides.

Approval is the only route to credit, and on stretch chores it is also the only
route to gaining a skill — the two loops feed each other.

## Scoring

Per-person score = sum of (estimated duration x difficulty) over approved
chores. Estimates are fixed on the chore, not self-reported at log time, so
the score can't be inflated by overstating time spent.

Scores reset monthly. The feed persists.

## History

The feed is append-only. Corrections — an effort override, a rejected
submission, a reassignment — add entries rather than replacing them, and record
who acted and when. This matters specifically because the admin can change
effort values, which moves scores.

## Admin powers

- Override effort values
- Resolve chores stuck after 2 rejections

## Deliberately out of scope

- Majority voting on approvals
- Escalation chains
- Restrictions on who the assignee may pick as approver
- Self-reported actual time
- Chore dependencies or blocked-by relationships
- Swaps between members

## Accepted trade-offs

- **Self-chosen approvers can rubber-stamp.** Mitigated by the public feed
  making approval patterns visible, not by mechanism.
- **AI estimation is a dependency** nothing else in the tool has. Manual entry
  must always work, so an AI failure can't block adding a chore. This is the
  safest thing to defer.
- **The admin can move scores** by overriding effort values. Append-only
  history makes this visible rather than preventing it.
- **Per-person scores invite competition.** A cooperative design would show
  household totals and no per-person figures. Chosen deliberately: visible
  individual contribution is the point, and the household is small enough that
  the feed provides context for any number.

## Open

- How the admin is chosen, and whether there can be more than one.

## Build order

Superseded by [backlog.md](backlog.md), which is the live order and is tracked
as GitHub issues.

The original order here front-loaded the whole verification loop and left the
scheduler until last. The backlog instead builds a thin end-to-end path first -
chores scheduled onto a calendar, assigned automatically, shown overdue when
missed, marked done - so that both halves of the premise are present early
rather than one being complete and the other absent.

The scheduler is still the bulk of the work.
