# Shared Household Chores Tool — Scope

## Problem

Households struggle to track who actually did what. Existing chore apps
mostly answer "whose turn is it"; this tool answers both that and "was it
actually done", with a verifiable record.

## Core concepts

### Household
Any number of members. One admin role.

### Chore
Each chore carries:

| Property | Values |
|---|---|
| Assignment mode | rotate / assign / claim |
| Recurrence | recurring (fixed interval) or one-off |
| Estimated duration | minutes |
| Difficulty | weight |
| Skill requirements | zero or more skills |

Anyone can add a chore to the shared list. Duration and difficulty are
AI-suggested, confirmed by household agreement, and overridable by the admin.

### Person
Each member has:
- a skill set (which chores they're qualified for)
- an availability calendar
- an opt-in flag for stretch-learning

## Assignment

Rotation runs through household members, filtered by skill requirements and
calendar availability.

When nobody is both skilled and available:
- **Default:** the chore is pushed to another day and flagged.
- **Alternative:** if a member has opted into stretch-learning, they may be
  assigned it despite lacking the skill.

A chore that nobody qualifies for and nobody opts into will keep deferring.
Surface this in the UI rather than deferring silently.

## Completion and approval

1. Assignee completes the chore and logs it with a photo.
2. Assignee picks an approver from the household.
3. Approver confirms or rejects.
4. On approval: the entry enters the public feed and scores.
5. On approval of a **stretch** chore: the skill is added to the assignee's
   skill set.
6. On rejection: back to the same person to redo.
7. After 2 rejections: the admin decides.

## Scoring

Per-person score = sum of (estimated duration x difficulty) over approved
chores. Estimates are fixed on the chore, not self-reported at log time, so
the score can't be inflated by overstating time spent.

Scores reset monthly. The feed persists.

## Admin powers

- Override effort values
- Resolve chores stuck after 2 rejections

## Deliberately out of scope

- Majority voting on approvals
- Escalation chains
- Restrictions on who the assignee may pick as approver
- Self-reported actual time

## Accepted trade-offs

- **Self-chosen approvers can rubber-stamp.** Mitigated by the public feed
  making approval patterns visible, not by mechanism.
- **AI estimation is a dependency** nothing else in the tool has. The tool
  functions with hand-entered values; this is the safest thing to defer.
- **The admin can move scores** by overriding effort values. Consider logging
  admin actions to the feed.

## Open

- How the admin is chosen, and whether there can be more than one.

## Build order

Ordered so there's always something demonstrable.

1. Chores, people, logging with photos
2. Approval and public feed
3. Scoring
4. Skills and calendars (data models only)
5. Scheduler — the largest piece
6. Stretch-learning (depends on 5 and 2)
7. AI estimation — optional

The scheduler is the bulk of the work. Items 1-3 form a usable tool on their
own if time runs short.
