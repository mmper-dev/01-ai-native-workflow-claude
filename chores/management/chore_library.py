"""The standard chore library, as plain Python data.

Kept out of the command that loads it so that task 33's AI-suggested durations
and difficulties, and any later edit to the list, have one place to change.
This module knows nothing about a household: `household`, `start_date` and
`fixed_member` are the loader's business.

Every entry is a repeating chore in rotate mode, and both of those are spelled
out per entry rather than filled in by the loader, because they are data the
loader validates rather than assumptions it makes.

Seasonal chores -- mowing the lawn, defrosting the freezer -- are deliberately
absent. Task 38's pause flag does not exist yet, so a household that wanted to
stop one for the winter could only delete it, and task 4 PROTECTs a definition
once it has occurrences. Add them when 38 lands.
"""

from chores.models import AssignmentMode, Recurrence

# Field names are ChoreDefinition's own, so an entry can be splatted straight
# into the model. Ordered roughly by how often the chore comes round.
CHORE_LIBRARY: tuple[dict[str, object], ...] = (
    {
        "name": "Wash the dishes",
        "estimated_minutes": 20,
        "difficulty": 1,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 1,
    },
    {
        "name": "Wipe down the kitchen surfaces",
        "estimated_minutes": 10,
        "difficulty": 1,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 2,
    },
    {
        "name": "Do a load of laundry",
        "estimated_minutes": 15,
        "difficulty": 2,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 3,
    },
    {
        "name": "Water the plants",
        "estimated_minutes": 10,
        "difficulty": 1,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 4,
    },
    {
        "name": "Take out the bins",
        "estimated_minutes": 10,
        "difficulty": 1,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 7,
    },
    {
        "name": "Vacuum the floors",
        "estimated_minutes": 30,
        "difficulty": 2,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 7,
    },
    {
        "name": "Clean the bathroom",
        "estimated_minutes": 35,
        "difficulty": 3,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 7,
    },
    {
        "name": "Change the bed sheets",
        "estimated_minutes": 15,
        "difficulty": 2,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 14,
    },
    {
        "name": "Mop the hard floors",
        "estimated_minutes": 25,
        "difficulty": 3,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 14,
    },
    {
        "name": "Dust the shelves and surfaces",
        "estimated_minutes": 20,
        "difficulty": 2,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 14,
    },
    {
        "name": "Clean out the fridge",
        "estimated_minutes": 30,
        "difficulty": 3,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 30,
    },
    {
        "name": "Clean the oven",
        "estimated_minutes": 60,
        "difficulty": 5,
        "assignment_mode": AssignmentMode.ROTATE,
        "recurrence": Recurrence.INTERVAL,
        "interval_days": 90,
    },
)
