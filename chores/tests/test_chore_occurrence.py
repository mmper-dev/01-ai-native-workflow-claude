"""Tests for issue #4 -- ChoreOccurrence and its frozen effort values.

One test per acceptance criterion on the issue, in the order they are listed
there, as `test_chore_definition.py` does. Where a criterion says a rule must
hold in the database as well as in `clean()`, there are two tests: one through
`full_clean()` and one through `objects.create()`, which is the path task 6's
generator, task 13's admin and task 35's seed take.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from chores.models import (
    AssignmentMode,
    ChoreDefinition,
    ChoreOccurrence,
    Household,
    Membership,
    OccurrenceState,
    Recurrence,
    User,
)

START = datetime.date(2026, 1, 5)
DUE = datetime.datetime(2026, 1, 5, 18, 0, tzinfo=datetime.UTC)


@pytest.fixture
def household(db):
    return Household.objects.create(name="Rose Cottage")


@pytest.fixture
def other_household(db):
    return Household.objects.create(name="Beach House")


@pytest.fixture
def member(db, household):
    user = User.objects.create_user(
        username="ana", email="ana@example.com", password="pw-for-tests"
    )
    Membership.objects.create(user=user, household=household)
    return user


@pytest.fixture
def outsider(db):
    return User.objects.create_user(
        username="ben", email="ben@example.com", password="pw-for-tests"
    )


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
    """An otherwise-valid, unassigned, pending occurrence."""
    fields = {"definition": definition, "due_at": DUE}
    fields.update(overrides)
    return ChoreOccurrence(**fields)


def create(definition, **overrides):
    occurrence = make(definition, **overrides)
    occurrence.save()
    return occurrence


# A required FK to ChoreDefinition, related_name="occurrences"


@pytest.mark.django_db
def test_occurrence_belongs_to_a_definition(definition):
    occurrence = create(definition)
    assert occurrence.definition == definition
    assert list(definition.occurrences.all()) == [occurrence]


@pytest.mark.django_db
def test_definition_is_required(definition):
    occurrence = make(definition)
    occurrence.definition = None
    with pytest.raises(ValidationError) as exc:
        occurrence.full_clean()
    assert "definition" in exc.value.message_dict


# assignee is a nullable FK to the user model, related_name="assigned_occurrences"


@pytest.mark.django_db
def test_assignee_points_at_the_user_model(definition, member):
    occurrence = create(definition, assignee=member)
    assert occurrence.assignee == member
    assert list(member.assigned_occurrences.all()) == [occurrence]


@pytest.mark.django_db
def test_assignee_is_nullable_for_claim_mode(definition):
    """A claim-mode chore has nobody on the hook until someone claims it."""
    occurrence = create(definition)
    occurrence.full_clean()
    assert occurrence.assignee is None


# due_at is a required UTC datetime


@pytest.mark.django_db
def test_due_at_is_required(definition):
    with pytest.raises(ValidationError) as exc:
        make(definition, due_at=None).full_clean()
    assert "due_at" in exc.value.message_dict


@pytest.mark.django_db
def test_due_at_is_stored_in_utc(definition):
    """A due time given in another zone comes back as the same instant in UTC."""
    athens = datetime.timezone(datetime.timedelta(hours=2))
    local = datetime.datetime(2026, 1, 5, 20, 0, tzinfo=athens)
    occurrence = create(definition, due_at=local)
    occurrence.refresh_from_db()
    assert occurrence.due_at.utcoffset() == datetime.timedelta(0)
    assert occurrence.due_at == datetime.datetime(2026, 1, 5, 18, 0, tzinfo=datetime.UTC)


# __str__, as every other model in chores/models.py defines one


@pytest.mark.django_db
def test_occurrence_renders_as_a_string(definition):
    assert str(create(definition)) == "Dishes due 2026-01-05 18:00"


# The household is reached through the definition, not duplicated


@pytest.mark.django_db
def test_household_is_not_a_field_on_the_occurrence(definition, household):
    field_names = {field.name for field in ChoreOccurrence._meta.get_fields()}
    assert "household" not in field_names
    assert create(definition).definition.household == household


# Effort values are copied from the definition on creation


@pytest.mark.django_db
def test_new_occurrence_copies_both_effort_values(definition):
    occurrence = create(definition)
    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == definition.estimated_minutes == 15
    assert occurrence.difficulty == definition.difficulty == 2


@pytest.mark.django_db
def test_the_copy_happens_on_objects_create_too(definition):
    """The admin and the seed command use this path, not save() on an instance."""
    occurrence = ChoreOccurrence.objects.create(definition=definition, due_at=DUE)
    occurrence.refresh_from_db()
    assert (occurrence.estimated_minutes, occurrence.difficulty) == (15, 2)


@pytest.mark.django_db
def test_explicit_effort_values_are_honoured(definition):
    occurrence = create(definition, estimated_minutes=90, difficulty=5)
    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == 90
    assert occurrence.difficulty == 5


@pytest.mark.django_db
def test_passing_only_difficulty_copies_estimated_minutes(definition):
    occurrence = create(definition, difficulty=4)
    occurrence.refresh_from_db()
    assert occurrence.difficulty == 4
    assert occurrence.estimated_minutes == 15


@pytest.mark.django_db
def test_passing_only_estimated_minutes_copies_difficulty(definition):
    occurrence = create(definition, estimated_minutes=90)
    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == 90
    assert occurrence.difficulty == 2


# The copy happens on creation only


@pytest.mark.django_db
def test_re_saving_an_existing_occurrence_never_re_copies(definition):
    """Task 5, 7 and 10 all re-save an occurrence; none may rewrite its score."""
    occurrence = create(definition)
    definition.estimated_minutes = 999
    definition.difficulty = 5
    definition.save()

    occurrence.save()

    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == 15
    assert occurrence.difficulty == 2


@pytest.mark.django_db
def test_re_saving_after_a_refresh_still_never_re_copies(definition):
    """Refreshing loses no state that the freeze depends on."""
    occurrence = create(definition)
    definition.estimated_minutes = 999
    definition.difficulty = 5
    definition.save()

    reloaded = ChoreOccurrence.objects.get(pk=occurrence.pk)
    reloaded.state = OccurrenceState.DONE
    reloaded.save()

    reloaded.refresh_from_db()
    assert reloaded.estimated_minutes == 15
    assert reloaded.difficulty == 2


@pytest.mark.django_db
def test_full_clean_on_an_existing_occurrence_never_re_copies(definition):
    occurrence = create(definition)
    definition.estimated_minutes = 999
    definition.difficulty = 5
    definition.save()

    reloaded = ChoreOccurrence.objects.get(pk=occurrence.pk)
    reloaded.full_clean()
    reloaded.save()

    reloaded.refresh_from_db()
    assert (reloaded.estimated_minutes, reloaded.difficulty) == (15, 2)


@pytest.mark.django_db
def test_editing_a_definition_does_not_change_an_existing_occurrence(definition):
    occurrence = create(definition)
    definition.estimated_minutes = 60
    definition.difficulty = 5
    definition.save()

    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == 15
    assert occurrence.difficulty == 2


@pytest.mark.django_db
def test_an_occurrence_created_after_the_edit_gets_the_new_values(definition):
    create(definition)
    definition.estimated_minutes = 60
    definition.difficulty = 5
    definition.save()

    later = create(definition, due_at=DUE + datetime.timedelta(days=1))
    later.refresh_from_db()
    assert (later.estimated_minutes, later.difficulty) == (60, 5)


# The frozen values carry CheckConstraints mirroring the definition's


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [0, -1])
def test_non_positive_estimated_minutes_fails_validation(definition, minutes):
    with pytest.raises(ValidationError) as exc:
        make(definition, estimated_minutes=minutes).full_clean()
    assert "estimated_minutes" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [0, -1])
def test_non_positive_estimated_minutes_is_rejected_by_the_database(definition, minutes):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(definition, estimated_minutes=minutes)


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
def test_difficulty_accepts_one_to_five(definition, difficulty):
    occurrence = make(definition, difficulty=difficulty)
    occurrence.full_clean()
    occurrence.save()
    assert occurrence.difficulty == difficulty


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [0, -1, 6, 99])
def test_difficulty_outside_one_to_five_fails_validation(definition, difficulty):
    with pytest.raises(ValidationError) as exc:
        make(definition, difficulty=difficulty).full_clean()
    assert "difficulty" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [0, -1, 6, 99])
def test_difficulty_outside_one_to_five_is_rejected_by_the_database(definition, difficulty):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(definition, difficulty=difficulty)


@pytest.mark.django_db
def test_the_effort_constraints_are_named_as_the_issue_says():
    names = {constraint.name for constraint in ChoreOccurrence._meta.constraints}
    assert "chore_occurrence_estimated_minutes_positive" in names
    assert "chore_occurrence_difficulty_in_range" in names


# state is exactly pending and done, defaulting to pending


@pytest.mark.django_db
def test_state_choices_are_exactly_pending_and_done():
    field = ChoreOccurrence._meta.get_field("state")
    assert [value for value, _label in field.choices] == ["pending", "done"]
    assert len(OccurrenceState.choices) == 2


@pytest.mark.django_db
def test_overdue_is_not_a_state():
    """AGENTS.md: an overdue occurrence is still pending and still assigned."""
    assert "overdue" not in OccurrenceState.values


@pytest.mark.django_db
def test_state_defaults_to_pending(definition):
    occurrence = create(definition)
    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.PENDING == "pending"


@pytest.mark.django_db
def test_done_is_a_valid_state(definition):
    occurrence = make(definition, state=OccurrenceState.DONE)
    occurrence.full_clean()
    occurrence.save()
    occurrence.refresh_from_db()
    assert occurrence.state == "done"


@pytest.mark.django_db
def test_an_unknown_state_fails_validation(definition):
    with pytest.raises(ValidationError) as exc:
        make(definition, state="overdue").full_clean()
    assert "state" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("state", ["overdue", "cancelled", ""])
def test_an_unknown_state_is_rejected_by_the_database(definition, state):
    """full_clean() is the only place Django checks choices; the admin and the
    generator write without it, so the rule is a CheckConstraint as well."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(definition, state=state)


@pytest.mark.django_db
def test_the_state_constraint_is_named_as_the_issue_says():
    names = {constraint.name for constraint in ChoreOccurrence._meta.constraints}
    assert "chore_occurrence_state_in_choices" in names


# Task 4 asserted here that `mark_done` and `overdue_at` did not exist yet --
# a boundary between two tasks rather than a rule about the model. Task 5 has
# landed and added both, so the assertion is gone and the behaviour is covered
# by `test_occurrence_lifecycle.py`.


# Integrity: PROTECT on both foreign keys


@pytest.mark.django_db
def test_deleting_an_assignee_is_blocked(definition, member):
    create(definition, assignee=member)
    with pytest.raises(ProtectedError):
        member.delete()
    assert User.objects.filter(pk=member.pk).exists()


@pytest.mark.django_db
def test_deleting_a_definition_with_occurrences_is_blocked(definition):
    create(definition)
    with pytest.raises(ProtectedError):
        definition.delete()
    assert ChoreDefinition.objects.filter(pk=definition.pk).exists()


# UniqueConstraint on (definition, due_at)


@pytest.mark.django_db
def test_two_occurrences_of_one_definition_cannot_share_a_due_at(definition):
    create(definition)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(definition)


@pytest.mark.django_db
def test_the_same_due_at_on_two_definitions_is_fine(household, definition):
    other = ChoreDefinition.objects.create(
        household=household,
        name="Bins",
        estimated_minutes=5,
        difficulty=1,
        assignment_mode=AssignmentMode.ROTATE,
        start_date=START,
    )
    create(definition)
    create(other)
    assert ChoreOccurrence.objects.filter(due_at=DUE).count() == 2


@pytest.mark.django_db
def test_one_definition_can_have_many_due_ats(definition):
    create(definition)
    create(definition, due_at=DUE + datetime.timedelta(days=7))
    assert definition.occurrences.count() == 2


@pytest.mark.django_db
def test_the_unique_constraint_is_named_as_the_issue_says():
    names = {constraint.name for constraint in ChoreOccurrence._meta.constraints}
    assert "unique_occurrence_per_definition_and_due_at" in names


# The assignee must have a Membership in the definition's household


@pytest.mark.django_db
def test_an_assignee_in_the_household_passes_validation(definition, member):
    occurrence = make(definition, assignee=member)
    occurrence.full_clean()
    occurrence.save()
    assert occurrence.assignee == member


@pytest.mark.django_db
def test_an_assignee_from_another_household_fails_validation(definition, other_household, outsider):
    Membership.objects.create(user=outsider, household=other_household)
    with pytest.raises(ValidationError) as exc:
        make(definition, assignee=outsider).full_clean()
    assert "assignee" in exc.value.message_dict


@pytest.mark.django_db
def test_an_assignee_with_no_membership_at_all_fails_validation(definition, outsider):
    with pytest.raises(ValidationError) as exc:
        make(definition, assignee=outsider).full_clean()
    assert "assignee" in exc.value.message_dict


@pytest.mark.django_db
def test_a_null_assignee_passes_validation(definition):
    """The household check only runs when an assignee is set."""
    occurrence = make(definition)
    occurrence.full_clean()
    occurrence.save()
    assert occurrence.assignee is None


@pytest.mark.django_db
def test_the_same_household_rule_is_not_maintained_after_the_fact(definition, member):
    """Checked on validation only -- task 36 covers an assignee who has left."""
    occurrence = make(definition, assignee=member)
    occurrence.full_clean()
    occurrence.save()
    Membership.objects.filter(user=member, household=definition.household).delete()
    occurrence.refresh_from_db()
    assert occurrence.assignee == member


# No photo field belongs here -- it is task 10's CompletionLog


@pytest.mark.django_db
def test_the_occurrence_has_no_photo_field():
    field_names = {field.name for field in ChoreOccurrence._meta.get_fields()}
    assert not field_names & {"photo", "completion_photo", "image"}
