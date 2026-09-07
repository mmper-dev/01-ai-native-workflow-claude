"""Tests for issue #2 -- Household and Membership.

One test per acceptance criterion on the issue, in the order they are listed
there, so a reviewer can read the two side by side.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from chores.models import Household, Membership, User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="ana", email="ana@example.com", password="pw-for-tests"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="ben", email="ben@example.com", password="pw-for-tests"
    )


@pytest.fixture
def household(db):
    return Household.objects.create(name="Rose Cottage")


# Household exists with a name; creating one with a blank name fails validation


@pytest.mark.django_db
def test_household_has_a_name(household):
    assert household.name == "Rose Cottage"
    assert str(household) == "Rose Cottage"


@pytest.mark.django_db
def test_blank_household_name_fails_validation():
    with pytest.raises(ValidationError) as exc:
        Household(name="").full_clean()
    assert "name" in exc.value.message_dict


@pytest.mark.django_db
def test_blank_household_name_is_also_rejected_by_the_database():
    """full_clean() is not on the path the admin or a data load takes."""
    with pytest.raises(IntegrityError):
        Household.objects.create(name="")


@pytest.mark.django_db
@pytest.mark.parametrize("blank_name", ["   ", "\t", "\n", " \t "])
def test_whitespace_only_household_name_fails_validation(blank_name):
    """A household called "   " reads as blank on every screen it appears on."""
    with pytest.raises(ValidationError) as exc:
        Household(name=blank_name).full_clean()
    assert "name" in exc.value.message_dict


@pytest.mark.django_db
def test_whitespace_only_household_name_is_rejected_by_the_database():
    with pytest.raises(IntegrityError):
        Household.objects.create(name="   ")


@pytest.mark.django_db
def test_surrounding_whitespace_is_stripped_from_a_household_name():
    house = Household.objects.create(name="  Rose Cottage  ")
    house.refresh_from_db()
    assert house.name == "Rose Cottage"


# Household has a timezone, defaulting to the project's TIME_ZONE


@pytest.mark.django_db
def test_household_timezone_defaults_to_the_project_timezone(settings):
    assert Household.objects.create(name="Default tz").timezone == settings.TIME_ZONE


@pytest.mark.django_db
@override_settings(TIME_ZONE="Europe/Athens")
def test_household_timezone_default_follows_a_changed_setting():
    """The default is a callable, so it is not frozen into the migration."""
    assert Household.objects.create(name="Athens tz").timezone == "Europe/Athens"


@pytest.mark.django_db
def test_household_timezone_can_be_overridden():
    house = Household.objects.create(name="Lisbon", timezone="Europe/Lisbon")
    house.full_clean()
    assert house.timezone == "Europe/Lisbon"


@pytest.mark.django_db
def test_unknown_household_timezone_fails_validation():
    with pytest.raises(ValidationError) as exc:
        Household(name="Nowhere", timezone="Mars/Olympus_Mons").full_clean()
    assert "timezone" in exc.value.message_dict


# Membership links a user to a household and carries roles


@pytest.mark.django_db
def test_membership_links_a_user_to_a_household(user, household):
    membership = Membership.objects.create(user=user, household=household)
    assert membership.user == user
    assert membership.household == household
    assert list(household.memberships.all()) == [membership]
    assert list(user.memberships.all()) == [membership]


# `admin` is an available role, and a membership can hold none, one, or several


@pytest.mark.django_db
def test_membership_can_hold_no_roles(user, household):
    membership = Membership.objects.create(user=user, household=household)
    membership.full_clean()
    assert membership.roles == []
    assert membership.is_admin is False


@pytest.mark.django_db
def test_membership_can_hold_the_admin_role(user, household):
    membership = Membership.objects.create(user=user, household=household, roles=[Membership.ADMIN])
    membership.full_clean()
    assert membership.has_role(Membership.ADMIN)
    assert membership.is_admin is True


@pytest.mark.django_db
def test_membership_can_hold_several_roles(user, household):
    """The criterion is none, one, or several -- this is the several case."""
    membership = Membership(
        user=user, household=household, roles=[Membership.ADMIN, Membership.USER]
    )
    membership.full_clean()
    membership.save()
    membership.refresh_from_db()
    assert membership.roles == [Membership.ADMIN, Membership.USER]
    assert membership.has_role(Membership.ADMIN)
    assert membership.has_role(Membership.USER)


@pytest.mark.django_db
def test_duplicate_roles_are_collapsed(user, household):
    """Roles are a set: storing the same role twice keeps one copy."""
    membership = Membership(user=user, household=household)
    membership.roles = [Membership.ADMIN, Membership.ADMIN]
    membership.save()
    membership.refresh_from_db()
    assert membership.roles == [Membership.ADMIN]


@pytest.mark.django_db
def test_holding_the_user_role_alone_does_not_make_someone_an_admin(user, household):
    membership = Membership.objects.create(user=user, household=household, roles=[Membership.USER])
    assert membership.is_admin is False


@pytest.mark.django_db
def test_unknown_role_fails_validation(user, household):
    with pytest.raises(ValidationError) as exc:
        Membership(user=user, household=household, roles=["landlord"]).full_clean()
    assert "roles" in exc.value.message_dict


@pytest.mark.django_db
def test_roles_must_be_a_list(user, household):
    with pytest.raises(ValidationError) as exc:
        Membership(user=user, household=household, roles="admin").full_clean()
    assert "roles" in exc.value.message_dict


# A second Membership for the same user and household raises IntegrityError


@pytest.mark.django_db
def test_duplicate_membership_raises_integrity_error(user, household):
    Membership.objects.create(user=user, household=household)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(user=user, household=household)


# The same user can hold memberships in two different households


@pytest.mark.django_db
def test_same_user_can_belong_to_two_households(user):
    first = Household.objects.create(name="Rose Cottage")
    second = Household.objects.create(name="Beach House")
    Membership.objects.create(user=user, household=first)
    Membership.objects.create(user=user, household=second)
    assert user.memberships.count() == 2


@pytest.mark.django_db
def test_two_users_can_belong_to_one_household(user, other_user, household):
    Membership.objects.create(user=user, household=household)
    Membership.objects.create(user=other_user, household=household)
    assert household.memberships.count() == 2


# Deleting a User that has a Membership is blocked by on_delete=PROTECT


@pytest.mark.django_db
def test_deleting_a_user_with_a_membership_is_blocked(user, household):
    from django.db.models import ProtectedError

    Membership.objects.create(user=user, household=household)
    with pytest.raises(ProtectedError):
        user.delete()
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_deleting_a_household_with_a_membership_is_blocked(user, household):
    """Not in the criteria, but #13 expects PROTECT here for the same reason."""
    from django.db.models import ProtectedError

    Membership.objects.create(user=user, household=household)
    with pytest.raises(ProtectedError):
        household.delete()
    assert Household.objects.filter(pk=household.pk).exists()


@pytest.mark.django_db
def test_a_user_with_no_membership_can_still_be_deleted(user):
    user.delete()
    assert not User.objects.filter(pk=user.pk).exists()
