"""Tests for issue #3 -- ChoreDefinition.

One test per acceptance criterion on the issue, in the order they are listed
there, so a reviewer can read the two side by side. Where a criterion says a
rule must hold in the database as well as in `clean()`, there are two tests:
one through `full_clean()` and one through `objects.create()`, which is the
path the admin and the seed command take.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import ProtectedError

from chores.models import (
    AssignmentMode,
    ChoreDefinition,
    Household,
    Membership,
    Recurrence,
    User,
)

START = datetime.date(2026, 1, 5)


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


def make(household, **overrides):
    """An otherwise-valid rotate-mode, one-off definition."""
    fields = {
        "household": household,
        "name": "Dishes",
        "estimated_minutes": 15,
        "difficulty": 2,
        "assignment_mode": AssignmentMode.ROTATE,
        "start_date": START,
        "recurrence": Recurrence.ONE_OFF,
    }
    fields.update(overrides)
    return ChoreDefinition(**fields)


def create(household, **overrides):
    chore = make(household, **overrides)
    chore.save()
    return chore


# A required FK to Household with on_delete=PROTECT


@pytest.mark.django_db
def test_definition_belongs_to_a_household(household):
    chore = create(household)
    assert chore.household == household
    assert list(household.chore_definitions.all()) == [chore]


@pytest.mark.django_db
def test_household_is_required(household):
    with pytest.raises(ValidationError) as exc:
        chore = make(household)
        chore.household = None
        chore.full_clean()
    assert "household" in exc.value.message_dict


@pytest.mark.django_db
def test_deleting_a_household_with_a_chore_is_blocked(household):
    create(household)
    with pytest.raises(ProtectedError):
        household.delete()
    assert Household.objects.filter(pk=household.pk).exists()


# name is required, and whitespace-only is rejected rather than stored


@pytest.mark.django_db
def test_definition_has_a_name(household):
    chore = create(household, name="Dishes")
    assert chore.name == "Dishes"
    assert str(chore) == "Dishes"


@pytest.mark.django_db
def test_blank_name_fails_validation(household):
    with pytest.raises(ValidationError) as exc:
        make(household, name="").full_clean()
    assert "name" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("blank_name", ["   ", "\t", "\n", " \t "])
def test_whitespace_only_name_fails_validation(household, blank_name):
    with pytest.raises(ValidationError) as exc:
        make(household, name=blank_name).full_clean()
    assert "name" in exc.value.message_dict


@pytest.mark.django_db
def test_blank_name_is_also_rejected_by_the_database(household):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ChoreDefinition.objects.create(
                household=household,
                name="",
                estimated_minutes=15,
                difficulty=2,
                assignment_mode=AssignmentMode.ROTATE,
                start_date=START,
            )


@pytest.mark.django_db
def test_whitespace_only_name_is_rejected_by_the_database(household):
    """save() strips first, so "   " reaches the database as "" and is caught."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ChoreDefinition.objects.create(
                household=household,
                name="   ",
                estimated_minutes=15,
                difficulty=2,
                assignment_mode=AssignmentMode.ROTATE,
                start_date=START,
            )


@pytest.mark.django_db
def test_surrounding_whitespace_is_stripped_from_a_name(household):
    chore = create(household, name="  Dishes  ")
    chore.refresh_from_db()
    assert chore.name == "Dishes"


# UniqueConstraint on (household, name)


@pytest.mark.django_db
def test_two_chores_in_one_household_cannot_share_a_name(household):
    create(household, name="Dishes")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, name="Dishes")


@pytest.mark.django_db
def test_two_households_can_each_have_a_chore_of_the_same_name(household, other_household):
    create(household, name="Dishes")
    create(other_household, name="Dishes")
    assert ChoreDefinition.objects.filter(name="Dishes").count() == 2


@pytest.mark.django_db
def test_names_differing_only_in_case_are_two_chores(household):
    """Matching is exact -- this is accepted rather than guarded."""
    create(household, name="Dishes")
    create(household, name="dishes")
    assert household.chore_definitions.count() == 2


# estimated_minutes is a positive integer


@pytest.mark.django_db
def test_definition_records_an_estimated_duration(household):
    assert create(household, estimated_minutes=45).estimated_minutes == 45


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [0, -1])
def test_non_positive_estimated_minutes_fails_validation(household, minutes):
    with pytest.raises(ValidationError) as exc:
        make(household, estimated_minutes=minutes).full_clean()
    assert "estimated_minutes" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [0, -1])
def test_non_positive_estimated_minutes_is_rejected_by_the_database(household, minutes):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, estimated_minutes=minutes)


# difficulty is an integer from 1 to 5


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
def test_difficulty_accepts_one_to_five(household, difficulty):
    chore = make(household, difficulty=difficulty)
    chore.full_clean()
    chore.save()
    assert chore.difficulty == difficulty


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [0, -1, 6, 99])
def test_difficulty_outside_one_to_five_fails_validation(household, difficulty):
    with pytest.raises(ValidationError) as exc:
        make(household, difficulty=difficulty).full_clean()
    assert "difficulty" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("difficulty", [0, -1, 6, 99])
def test_difficulty_outside_one_to_five_is_rejected_by_the_database(household, difficulty):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, difficulty=difficulty)


# assignment_mode is required and is one of rotate, assign, claim


@pytest.mark.django_db
def test_assignment_modes_are_declared_as_choices():
    field = ChoreDefinition._meta.get_field("assignment_mode")
    assert [value for value, _label in field.choices] == ["rotate", "assign", "claim"]


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [AssignmentMode.ROTATE, AssignmentMode.CLAIM])
def test_rotate_and_claim_definitions_are_valid(household, mode):
    chore = make(household, assignment_mode=mode)
    chore.full_clean()
    chore.save()
    assert chore.assignment_mode == mode


@pytest.mark.django_db
def test_assignment_mode_is_required(household):
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode="").full_clean()
    assert "assignment_mode" in exc.value.message_dict


@pytest.mark.django_db
def test_unknown_assignment_mode_fails_validation(household):
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode="lottery").full_clean()
    assert "assignment_mode" in exc.value.message_dict


# fixed_member is a nullable FK to the user model with on_delete=PROTECT


@pytest.mark.django_db
def test_fixed_member_points_at_the_user_model(member, household):
    chore = create(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=member)
    assert chore.fixed_member == member
    assert list(member.fixed_chore_definitions.all()) == [chore]


@pytest.mark.django_db
def test_fixed_member_is_nullable(household):
    assert create(household).fixed_member is None


@pytest.mark.django_db
def test_deleting_a_fixed_member_is_blocked(member, household):
    create(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=member)
    with pytest.raises(ProtectedError):
        member.delete()
    assert User.objects.filter(pk=member.pk).exists()


# assign mode names a fixed member; without one it fails validation


@pytest.mark.django_db
def test_assign_mode_with_a_fixed_member_is_valid(member, household):
    chore = make(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=member)
    chore.full_clean()
    chore.save()
    assert chore.fixed_member == member


@pytest.mark.django_db
def test_assign_mode_without_a_fixed_member_fails_validation(household):
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode=AssignmentMode.ASSIGN).full_clean()
    assert "fixed_member" in exc.value.message_dict


# rotate and claim have no fixed member; naming one fails validation


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [AssignmentMode.ROTATE, AssignmentMode.CLAIM])
def test_non_assign_mode_with_a_fixed_member_fails_validation(member, household, mode):
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode=mode, fixed_member=member).full_clean()
    assert "fixed_member" in exc.value.message_dict


# Both pairing rules also hold as CheckConstraints


@pytest.mark.django_db
def test_assign_mode_without_a_fixed_member_is_rejected_by_the_database(household):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, assignment_mode=AssignmentMode.ASSIGN)


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [AssignmentMode.ROTATE, AssignmentMode.CLAIM])
def test_non_assign_mode_with_a_fixed_member_is_rejected_by_the_database(member, household, mode):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, assignment_mode=mode, fixed_member=member)


# The fixed member must have a Membership in the definition's household


@pytest.mark.django_db
def test_fixed_member_from_another_household_fails_validation(household, other_household, outsider):
    Membership.objects.create(user=outsider, household=other_household)
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=outsider).full_clean()
    assert "fixed_member" in exc.value.message_dict


@pytest.mark.django_db
def test_fixed_member_with_no_membership_at_all_fails_validation(household, outsider):
    with pytest.raises(ValidationError) as exc:
        make(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=outsider).full_clean()
    assert "fixed_member" in exc.value.message_dict


@pytest.mark.django_db
def test_the_same_household_rule_is_not_maintained_after_the_fact(member, household):
    """It is checked on validation only -- task 7 covers a member who has left."""
    chore = make(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=member)
    chore.full_clean()
    chore.save()
    Membership.objects.filter(user=member, household=household).delete()
    chore.refresh_from_db()
    assert chore.fixed_member == member


# start_date is a required local calendar date, not a datetime


@pytest.mark.django_db
def test_start_date_is_a_date_field_not_a_datetime_field():
    field = ChoreDefinition._meta.get_field("start_date")
    assert isinstance(field, models.DateField)
    assert not isinstance(field, models.DateTimeField)


@pytest.mark.django_db
def test_start_date_is_stored_as_a_plain_date(household):
    chore = create(household, start_date=datetime.date(2026, 3, 1))
    chore.refresh_from_db()
    assert chore.start_date == datetime.date(2026, 3, 1)


@pytest.mark.django_db
def test_start_date_is_required(household):
    with pytest.raises(ValidationError) as exc:
        make(household, start_date=None).full_clean()
    assert "start_date" in exc.value.message_dict


# Recurrence is one-off or a fixed interval in whole days


@pytest.mark.django_db
def test_recurrence_choices_are_one_off_and_interval():
    field = ChoreDefinition._meta.get_field("recurrence")
    assert [value for value, _label in field.choices] == ["one_off", "interval"]


@pytest.mark.django_db
def test_a_one_off_definition_is_valid(household):
    chore = make(household, recurrence=Recurrence.ONE_OFF)
    chore.full_clean()
    chore.save()
    assert chore.interval_days is None


@pytest.mark.django_db
def test_an_interval_definition_is_valid(household):
    chore = make(household, recurrence=Recurrence.INTERVAL, interval_days=7)
    chore.full_clean()
    chore.save()
    chore.refresh_from_db()
    assert chore.interval_days == 7


# The recurrence pairing rules, in clean() and as CheckConstraints


@pytest.mark.django_db
def test_interval_without_interval_days_fails_validation(household):
    with pytest.raises(ValidationError) as exc:
        make(household, recurrence=Recurrence.INTERVAL).full_clean()
    assert "interval_days" in exc.value.message_dict


@pytest.mark.django_db
def test_interval_without_interval_days_is_rejected_by_the_database(household):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, recurrence=Recurrence.INTERVAL)


@pytest.mark.django_db
def test_one_off_with_interval_days_fails_validation(household):
    with pytest.raises(ValidationError) as exc:
        make(household, recurrence=Recurrence.ONE_OFF, interval_days=7).full_clean()
    assert "interval_days" in exc.value.message_dict


@pytest.mark.django_db
def test_one_off_with_interval_days_is_rejected_by_the_database(household):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, recurrence=Recurrence.ONE_OFF, interval_days=7)


# interval_days, when set, is a positive integer


@pytest.mark.django_db
@pytest.mark.parametrize("days", [0, -1])
def test_non_positive_interval_days_fails_validation(household, days):
    with pytest.raises(ValidationError) as exc:
        make(household, recurrence=Recurrence.INTERVAL, interval_days=days).full_clean()
    assert "interval_days" in exc.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("days", [0, -1])
def test_non_positive_interval_days_is_rejected_by_the_database(household, days):
    """Zero would make task 6's generator return the same date forever."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            create(household, recurrence=Recurrence.INTERVAL, interval_days=days)


# Creation is not gated on a role


@pytest.mark.django_db
def test_a_member_with_no_roles_can_add_a_chore(member, household):
    membership = Membership.objects.get(user=member, household=household)
    assert membership.roles == []
    chore = make(household, name="Bins")
    chore.full_clean()
    chore.save()
    assert household.chore_definitions.filter(name="Bins").exists()


@pytest.mark.django_db
def test_nothing_on_the_model_asks_who_is_adding_the_chore():
    """No creator or role field: the model does not know or care who acted."""
    field_names = {field.name for field in ChoreDefinition._meta.get_fields()}
    assert not field_names & {"created_by", "role", "author"}
