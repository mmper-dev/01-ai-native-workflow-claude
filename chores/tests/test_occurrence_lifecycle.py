"""Tests for issue #5 -- the occurrence transitions and the overdue flag.

One test per acceptance criterion on the issue, in the order they are listed
there, matching the style of `test_chore_occurrence.py`.

Every clock here is a fixed `datetime` passed straight into the transition.
`time-machine` is a dev dependency and task 12 uses it, but nothing in this
task needs the process clock to move.
"""

import ast
import datetime
import importlib
import inspect
import pathlib
import re

import pytest
from django.core.management import call_command
from django.db import migrations
from django.db import models as django_models

from chores.models import (
    ALLOWED_TRANSITIONS,
    AssignmentMode,
    ChoreDefinition,
    ChoreOccurrence,
    Household,
    IllegalTransition,
    Membership,
    OccurrenceState,
    Recurrence,
    User,
)

START = datetime.date(2026, 1, 5)
DUE = datetime.datetime(2026, 1, 5, 18, 0, tzinfo=datetime.UTC)
LATE = datetime.datetime(2026, 1, 6, 9, 0, tzinfo=datetime.UTC)
LATER = datetime.datetime(2026, 1, 7, 9, 0, tzinfo=datetime.UTC)

CHORES = pathlib.Path(inspect.getfile(ChoreOccurrence)).parent
ASSIGNS_STATE_OR_FLAG = re.compile(r"\.state\s*=|\.overdue_at\s*=")


@pytest.fixture
def household(db):
    return Household.objects.create(name="Rose Cottage")


@pytest.fixture
def member(db, household):
    user = User.objects.create_user(
        username="ana", email="ana@example.com", password="pw-for-tests"
    )
    Membership.objects.create(user=user, household=household)
    return user


@pytest.fixture
def other_member(db, household):
    user = User.objects.create_user(
        username="ben", email="ben@example.com", password="pw-for-tests"
    )
    Membership.objects.create(user=user, household=household)
    return user


@pytest.fixture
def definition(db, household):
    return ChoreDefinition.objects.create(
        household=household,
        name="Dishes",
        estimated_minutes=15,
        difficulty=2,
        assignment_mode=AssignmentMode.ROTATE,
        start_date=START,
        recurrence=Recurrence.ONE_OFF,
    )


def make(definition, **overrides):
    """An otherwise-valid, unassigned, pending occurrence, unsaved."""
    fields = {"definition": definition, "due_at": DUE}
    fields.update(overrides)
    return ChoreOccurrence(**fields)


def create(definition, **overrides):
    occurrence = make(definition, **overrides)
    occurrence.save()
    return occurrence


def transition_source(name: str) -> str:
    return inspect.getsource(getattr(ChoreOccurrence, name))


# -- The field ---------------------------------------------------------------


@pytest.mark.django_db
def test_overdue_at_is_a_nullable_utc_timestamp_defaulting_to_none(definition):
    field = ChoreOccurrence._meta.get_field("overdue_at")
    assert isinstance(field, django_models.DateTimeField)
    assert field.null is True
    assert field.blank is True
    assert field.default is None
    assert "UTC" in field.help_text
    assert "flag, not a state" in field.help_text

    occurrence = create(definition)
    occurrence.refresh_from_db()
    assert occurrence.overdue_at is None


@pytest.mark.django_db
def test_no_check_constraint_mentions_overdue_at():
    """`overdue_at` is legal against either state, so there is no invariant.

    A done occurrence keeps the record that it was late.
    """
    names = {constraint.name for constraint in ChoreOccurrence._meta.constraints}
    assert not any("overdue" in name for name in names)
    assert names == {
        "chore_occurrence_estimated_minutes_positive",
        "chore_occurrence_difficulty_in_range",
        "chore_occurrence_state_in_choices",
        "unique_occurrence_per_definition_and_due_at",
    }


def test_the_migration_adds_one_nullable_column_and_nothing_else():
    """Existing rows get NULL, so no data migration is needed."""
    module = importlib.import_module("chores.migrations.0006_choreoccurrence_overdue_at")
    operations = module.Migration.operations

    assert len(operations) == 1
    operation = operations[0]
    assert isinstance(operation, migrations.AddField)
    assert (operation.model_name, operation.name) == ("choreoccurrence", "overdue_at")
    assert operation.field.null is True
    assert operation.field.default is None


@pytest.mark.django_db
def test_makemigrations_reports_nothing_missing():
    """A model change without its migration would break task 12's deploy."""
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


@pytest.mark.django_db
def test_migrate_applies_cleanly(definition):
    """pytest-django built this test database by running every migration.

    Reaching a row through the new column proves 0006 applied, and that an
    occurrence created before it would have been left NULL.
    """
    create(definition)
    assert ChoreOccurrence.objects.filter(overdue_at__isnull=True).count() == 1


# -- The transitions ---------------------------------------------------------


def test_the_transitions_are_the_only_writers_of_state_and_overdue_at():
    """grep -rn "\\.state\\s*=|\\.overdue_at\\s*=" chores/ --include=*.py

    Only the two transition bodies, once the tests are set aside: task 4's
    tests assign `state` directly to exercise the column and its constraint.
    """
    inside = sum(
        len(ASSIGNS_STATE_OR_FLAG.findall(transition_source(name)))
        for name in ("mark_done", "mark_overdue")
    )
    assert inside == 2

    total = 0
    for path in CHORES.rglob("*.py"):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        total += len(ASSIGNS_STATE_OR_FLAG.findall(path.read_text(encoding="utf-8")))
    assert total == inside


@pytest.mark.django_db
def test_each_transition_saves_only_the_field_it_wrote(monkeypatch, definition, member):
    """A plain save() would write a possibly stale instance back in full."""
    calls: list[list[str] | None] = []
    original = ChoreOccurrence.save

    def spy(self, *args, **kwargs):
        calls.append(kwargs.get("update_fields"))
        return original(self, *args, **kwargs)

    occurrence = create(definition, assignee=member)
    monkeypatch.setattr(ChoreOccurrence, "save", spy)

    occurrence.mark_overdue(now=LATE)
    occurrence.mark_done(now=LATER)

    assert calls == [["overdue_at"], ["state"]]


def test_neither_transition_calls_full_clean_or_opens_a_transaction():
    """Task 10 wraps the state change and its CompletionLog and owns that."""
    for name in ("mark_done", "mark_overdue"):
        source = transition_source(name)
        assert "full_clean" not in source
        assert "atomic" not in source


@pytest.mark.django_db
def test_a_transition_on_an_unsaved_instance_is_rejected(definition, member):
    """An accidental insert would also stamp effort values, per task 4."""
    before = ChoreOccurrence.objects.count()
    unsaved = make(definition, assignee=member)

    with pytest.raises(IllegalTransition):
        unsaved.mark_done(now=LATER)
    with pytest.raises(IllegalTransition):
        unsaved.mark_overdue(now=LATE)

    assert ChoreOccurrence.objects.count() == before


@pytest.mark.django_db
def test_no_transition_re_reads_the_definition_or_re_freezes_effort(definition, member):
    occurrence = create(definition, assignee=member)
    definition.estimated_minutes = 999
    definition.difficulty = 5
    definition.save()

    occurrence.mark_overdue(now=LATE)
    occurrence.mark_done(now=LATER)

    occurrence.refresh_from_db()
    assert (occurrence.estimated_minutes, occurrence.difficulty) == (15, 2)


# -- The guard ---------------------------------------------------------------


def test_the_allowed_moves_are_held_as_data():
    """Adding a state later must be a new entry, not a rewrite of the guard."""
    assert ALLOWED_TRANSITIONS == {OccurrenceState.PENDING: frozenset({OccurrenceState.DONE})}
    assert isinstance(ALLOWED_TRANSITIONS, dict)


@pytest.mark.django_db
def test_the_rejection_names_the_occurrence_and_the_states(definition, member):
    assert issubclass(IllegalTransition, Exception)

    occurrence = create(definition, assignee=member)
    occurrence.mark_done(now=LATER)

    with pytest.raises(IllegalTransition) as exc:
        occurrence.mark_done(now=LATER)

    message = str(exc.value)
    assert str(occurrence) in message
    assert "pending" not in message
    assert message.count("done") >= 2


def test_no_state_machine_library_is_used():
    source = pathlib.Path(inspect.getfile(ChoreOccurrence)).read_text(encoding="utf-8")
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imported & {"django_fsm", "fsm", "transitions", "statemachine", "viewflow"}


# -- mark_done ---------------------------------------------------------------


@pytest.mark.django_db
def test_mark_done_completes_a_pending_assigned_occurrence(definition, member):
    occurrence = create(definition, assignee=member)

    assert occurrence.mark_done(now=LATER) is True

    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.DONE


@pytest.mark.django_db
def test_mark_done_on_an_already_done_occurrence_raises(definition, member):
    occurrence = create(definition, assignee=member)
    occurrence.mark_done(now=LATER)
    before = ChoreOccurrence.objects.values().get(pk=occurrence.pk)

    with pytest.raises(IllegalTransition):
        occurrence.mark_done(now=LATER)

    assert ChoreOccurrence.objects.values().get(pk=occurrence.pk) == before


@pytest.mark.django_db
def test_mark_done_without_an_assignee_raises(definition):
    """There is nobody to credit. Task 11 and task 41 are the routes to one."""
    occurrence = create(definition)

    with pytest.raises(IllegalTransition):
        occurrence.mark_done(now=LATER)

    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.PENDING


@pytest.mark.django_db
def test_mark_done_keeps_an_existing_overdue_at_exactly(definition, member):
    """Clearing it would erase the record that the chore was late."""
    occurrence = create(definition, assignee=member)
    occurrence.mark_overdue(now=LATE)

    assert occurrence.mark_done(now=LATER) is True

    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.DONE
    assert occurrence.overdue_at == LATE


@pytest.mark.django_db
def test_mark_done_writes_no_completion_time_or_author(definition, member):
    """Both belong to task 10's CompletionLog, not to a column here."""
    field_names = {field.name for field in ChoreOccurrence._meta.get_fields()}
    assert not field_names & {"done_at", "completed_at", "completed_by", "done_by"}

    occurrence = create(definition, assignee=member)
    occurrence.mark_done(now=LATER)
    occurrence.refresh_from_db()
    assert LATER not in set(ChoreOccurrence.objects.values().get(pk=occurrence.pk).values())


# -- mark_overdue ------------------------------------------------------------


@pytest.mark.django_db
def test_mark_overdue_flags_a_pending_occurrence(definition, member):
    occurrence = create(definition, assignee=member)

    assert occurrence.mark_overdue(now=LATE) is True

    occurrence.refresh_from_db()
    assert occurrence.overdue_at == LATE
    assert occurrence.state == OccurrenceState.PENDING
    assert occurrence.assignee == member


@pytest.mark.django_db
def test_a_second_mark_overdue_is_an_idempotent_no_op(definition, member):
    """Task 12's loop passes over the same rows and counts what changed."""
    occurrence = create(definition, assignee=member)
    occurrence.mark_overdue(now=LATE)

    assert occurrence.mark_overdue(now=LATER) is False

    occurrence.refresh_from_db()
    assert occurrence.overdue_at == LATE


@pytest.mark.django_db
def test_mark_overdue_on_a_done_occurrence_raises(definition, member):
    occurrence = create(definition, assignee=member)
    occurrence.mark_done(now=LATER)

    with pytest.raises(IllegalTransition):
        occurrence.mark_overdue(now=LATER)

    occurrence.refresh_from_db()
    assert occurrence.overdue_at is None


@pytest.mark.django_db
def test_overdue_never_becomes_a_third_state(definition, member):
    """AGENTS.md: an overdue occurrence is still pending and still owed."""
    occurrence = create(definition, assignee=member)
    occurrence.mark_overdue(now=LATE)

    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.PENDING
    assert occurrence.assignee == member
    assert OccurrenceState.values == ["pending", "done"]


# -- The clock ---------------------------------------------------------------


def test_now_is_required_keyword_only_and_never_defaulted():
    source = pathlib.Path(inspect.getfile(ChoreOccurrence)).read_text(encoding="utf-8")
    assert not re.search(r"timezone\.now|datetime\.now", source)

    for name in ("mark_done", "mark_overdue"):
        signature = inspect.signature(getattr(ChoreOccurrence, name))
        parameter = signature.parameters["now"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


@pytest.mark.django_db
def test_a_naive_now_is_rejected_naming_the_argument(definition, member):
    """USE_TZ is on, so a naive value would silently shift the timestamp."""
    occurrence = create(definition, assignee=member)
    naive = datetime.datetime(2026, 1, 6, 9, 0)

    for transition in (occurrence.mark_overdue, occurrence.mark_done):
        with pytest.raises(ValueError, match="now"):
            transition(now=naive)

    occurrence.refresh_from_db()
    assert occurrence.overdue_at is None
    assert occurrence.state == OccurrenceState.PENDING


@pytest.mark.django_db
def test_a_now_before_due_at_is_accepted_and_stored(definition, member):
    """Deciding a chore has gone late is task 12's job, not this one's."""
    early = DUE - datetime.timedelta(days=2)
    occurrence = create(definition, assignee=member)

    assert occurrence.mark_overdue(now=early) is True

    occurrence.refresh_from_db()
    assert occurrence.overdue_at == early


# -- The assignee ------------------------------------------------------------


@pytest.mark.django_db
def test_no_transition_changes_the_assignee(definition, member, other_member):
    """Overdue never silently reassigns; task 41 is the only route."""
    occurrence = create(definition, assignee=member)

    occurrence.mark_overdue(now=LATE)
    occurrence.mark_done(now=LATER)

    occurrence.refresh_from_db()
    assert occurrence.assignee == member
    assert occurrence.assignee != other_member
