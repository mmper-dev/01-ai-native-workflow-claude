"""Tests for issue #35 -- the preloaded chore library.

One test per acceptance criterion on the issue, in the order they are listed
there, so a reviewer can read the two side by side.

The command is driven through `call_command` with a command instance rather
than by name, because that is how the clock and the library data are injected.
Every case that must fail asserts on `CommandError`, which is what makes the
real command line exit non-zero, and then asserts the household was left alone.
"""

import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from chores.management.chore_library import CHORE_LIBRARY
from chores.management.commands.load_chore_library import Command
from chores.models import (
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    AssignmentMode,
    ChoreDefinition,
    Household,
    Recurrence,
)

# 23:30 UTC on the 5th is already 12:30 on the 6th in Auckland, so a command
# that read UTC's date would be a day behind for this household.
PINNED_UTC = datetime.datetime(2026, 1, 5, 23, 30, tzinfo=datetime.UTC)
AUCKLAND_DATE = datetime.date(2026, 1, 6)


@pytest.fixture
def household(db):
    return Household.objects.create(name="Rose Cottage", timezone="Pacific/Auckland")


@pytest.fixture
def other_household(db):
    return Household.objects.create(name="Beach House", timezone="UTC")


def pinned_clock(moment=PINNED_UTC):
    return lambda: moment


def load(*args, clock=None, library=None, **options):
    """Run the command, returning what it wrote to stdout."""
    out = StringIO()
    command = Command(clock=clock or pinned_clock(), library=library)
    call_command(command, *args, stdout=out, **options)
    return out.getvalue()


def names_in(household):
    return set(household.chore_definitions.values_list("name", flat=True))


# The command name and its argument


@pytest.mark.django_db
def test_the_command_loads_a_library_into_the_named_household(household):
    load("Rose Cottage")
    assert household.chore_definitions.count() == len(CHORE_LIBRARY)
    assert names_in(household) == {entry["name"] for entry in CHORE_LIBRARY}


@pytest.mark.django_db
def test_the_command_is_registered_under_its_name(household):
    """QA runs `manage.py load_chore_library <household>`, so the name matters."""
    call_command("load_chore_library", "Rose Cottage", stdout=StringIO())
    assert household.chore_definitions.count() == len(CHORE_LIBRARY)


@pytest.mark.django_db
def test_only_the_named_household_is_filled(household, other_household):
    load("Rose Cottage")
    assert other_household.chore_definitions.count() == 0


# No argument, or a name that does not exist


@pytest.mark.django_db
def test_no_argument_fails_and_lists_the_households_that_exist(household, other_household):
    with pytest.raises(CommandError) as exc:
        load()
    assert "Rose Cottage" in str(exc.value)
    assert "Beach House" in str(exc.value)
    assert ChoreDefinition.objects.count() == 0


@pytest.mark.django_db
def test_no_argument_does_not_pick_the_first_household(household, other_household):
    with pytest.raises(CommandError):
        load()
    assert Household.objects.count() == 2


@pytest.mark.django_db
def test_an_unknown_household_fails_and_lists_the_households_that_exist(household):
    with pytest.raises(CommandError) as exc:
        load("Nowhere House")
    assert "Nowhere House" in str(exc.value)
    assert "Rose Cottage" in str(exc.value)
    assert ChoreDefinition.objects.count() == 0


@pytest.mark.django_db
def test_an_unknown_household_is_not_created(household):
    with pytest.raises(CommandError):
        load("Nowhere House")
    assert not Household.objects.filter(name="Nowhere House").exists()
    assert Household.objects.count() == 1


@pytest.mark.django_db
def test_a_command_error_is_what_fails_rather_than_a_bare_exception(db):
    """CommandError is what makes manage.py exit non-zero with a clean message."""
    with pytest.raises(CommandError) as exc:
        load("Rose Cottage")
    assert exc.value.returncode != 0


# Household.name is not unique, so a name can match more than one


@pytest.mark.django_db
def test_an_ambiguous_household_name_fails_and_writes_nothing(household):
    twin = Household.objects.create(name="Rose Cottage", timezone="UTC")
    with pytest.raises(CommandError) as exc:
        load("Rose Cottage")
    message = str(exc.value)
    assert f"id={household.pk}" in message
    assert f"id={twin.pk}" in message
    assert ChoreDefinition.objects.count() == 0


# Every entry sets the fields #3 provides, with values in range


@pytest.mark.django_db
@pytest.mark.parametrize(
    "keyword",
    ["dishes", "bins", "bathroom", "vacuum", "laundry", "sheets"],
)
def test_the_library_covers_the_chores_the_backlog_names(household, keyword):
    load("Rose Cottage")
    lowered = [name.lower() for name in names_in(household)]
    assert any(keyword in name for name in lowered), keyword


@pytest.mark.django_db
def test_every_definition_has_a_usable_effort_estimate(household):
    load("Rose Cottage")
    for definition in household.chore_definitions.all():
        assert definition.estimated_minutes >= 1
        assert MIN_DIFFICULTY <= definition.difficulty <= MAX_DIFFICULTY


@pytest.mark.django_db
def test_every_definition_repeats_on_a_whole_number_of_days(household):
    load("Rose Cottage")
    for definition in household.chore_definitions.all():
        assert definition.recurrence == Recurrence.INTERVAL
        assert isinstance(definition.interval_days, int)
        assert definition.interval_days >= 1


@pytest.mark.django_db
def test_every_definition_rotates_and_names_no_fixed_member(household):
    load("Rose Cottage")
    for definition in household.chore_definitions.all():
        assert definition.assignment_mode == AssignmentMode.ROTATE
        assert definition.fixed_member is None


@pytest.mark.django_db
def test_the_library_data_is_a_module_of_its_own():
    """Task 33's estimates and any later edit change one place, not the loader."""
    from chores.management import chore_library

    assert chore_library.__name__ != Command.__module__
    assert len(chore_library.CHORE_LIBRARY) >= 6
    names = [entry["name"] for entry in chore_library.CHORE_LIBRARY]
    assert len(names) == len(set(names))


# full_clean() on every entry, and the guard that proves it


@pytest.mark.django_db
def test_an_entry_with_an_unknown_assignment_mode_fails_and_writes_nothing(household):
    """#47 records there is no database guard on the choice fields.

    full_clean() is therefore the only thing standing between a typo in the
    library data and a row in the table, so this asserts it is actually called.
    """
    broken = [{**CHORE_LIBRARY[0], "assignment_mode": "lottery"}]
    with pytest.raises(CommandError) as exc:
        load("Rose Cottage", library=broken)
    assert "assignment_mode" in str(exc.value)
    assert household.chore_definitions.count() == 0


@pytest.mark.django_db
def test_an_entry_with_an_unknown_recurrence_fails_and_writes_nothing(household):
    broken = [{**CHORE_LIBRARY[0], "recurrence": "fortnightly"}]
    with pytest.raises(CommandError) as exc:
        load("Rose Cottage", library=broken)
    assert "recurrence" in str(exc.value)
    assert household.chore_definitions.count() == 0


# The load is one transaction


@pytest.mark.django_db
def test_a_bad_entry_part_way_down_leaves_the_household_as_it_was(household):
    library = [CHORE_LIBRARY[0], {**CHORE_LIBRARY[1], "difficulty": 99}, CHORE_LIBRARY[2]]
    with pytest.raises(CommandError):
        load("Rose Cottage", library=library)
    assert household.chore_definitions.count() == 0


@pytest.mark.django_db
def test_a_failure_does_not_disturb_definitions_the_household_already_had(household):
    load("Rose Cottage", library=[CHORE_LIBRARY[0]])
    with pytest.raises(CommandError):
        load("Rose Cottage", library=[{**CHORE_LIBRARY[1], "estimated_minutes": 0}])
    assert names_in(household) == {CHORE_LIBRARY[0]["name"]}


# Running twice creates nothing the second time


@pytest.mark.django_db
def test_a_second_load_creates_nothing(household):
    load("Rose Cottage")
    count = household.chore_definitions.count()
    load("Rose Cottage")
    assert household.chore_definitions.count() == count


@pytest.mark.django_db
def test_a_second_load_does_not_rewrite_the_rows_it_skips(household):
    """The first load's start_date survives, so #6's grid does not move."""
    load("Rose Cottage")
    later = pinned_clock(PINNED_UTC + datetime.timedelta(days=40))
    load("Rose Cottage", clock=later)
    start_dates = set(household.chore_definitions.values_list("start_date", flat=True))
    assert start_dates == {AUCKLAND_DATE}


@pytest.mark.django_db
def test_a_partly_loaded_household_gains_only_what_it_lacks(household):
    ChoreDefinition.objects.create(
        household=household,
        name=CHORE_LIBRARY[0]["name"],
        estimated_minutes=99,
        difficulty=5,
        assignment_mode=AssignmentMode.CLAIM,
        start_date=datetime.date(2020, 1, 1),
        recurrence=Recurrence.ONE_OFF,
    )
    load("Rose Cottage")
    assert household.chore_definitions.count() == len(CHORE_LIBRARY)
    kept = household.chore_definitions.get(name=CHORE_LIBRARY[0]["name"])
    assert kept.estimated_minutes == 99
    assert kept.assignment_mode == AssignmentMode.CLAIM
    assert kept.start_date == datetime.date(2020, 1, 1)


@pytest.mark.django_db
def test_matching_is_case_sensitive(household):
    """Names differing only in case are two chores -- #3's constraint says so."""
    library_name = CHORE_LIBRARY[0]["name"]
    ChoreDefinition.objects.create(
        household=household,
        name=library_name.lower(),
        estimated_minutes=10,
        difficulty=1,
        assignment_mode=AssignmentMode.ROTATE,
        start_date=datetime.date(2020, 1, 1),
        recurrence=Recurrence.ONE_OFF,
    )
    load("Rose Cottage")
    assert {library_name, library_name.lower()} <= names_in(household)
    assert household.chore_definitions.count() == len(CHORE_LIBRARY) + 1


@pytest.mark.django_db
def test_the_help_states_what_happens_after_a_rename():
    help_text = Command.help.lower()
    assert "rename" in help_text
    assert "case-sensitive" in help_text


# start_date is today, in the household's own timezone, from an injected clock


@pytest.mark.django_db
def test_start_date_is_the_households_local_date_not_utcs(household):
    load("Rose Cottage", clock=pinned_clock())
    start_dates = set(household.chore_definitions.values_list("start_date", flat=True))
    assert start_dates == {AUCKLAND_DATE}
    assert PINNED_UTC.date() != AUCKLAND_DATE


@pytest.mark.django_db
def test_a_household_in_another_timezone_gets_its_own_local_date(other_household):
    """The same instant, a different household: in UTC it is still the 5th."""
    load("Beach House", clock=pinned_clock())
    start_dates = set(other_household.chore_definitions.values_list("start_date", flat=True))
    assert start_dates == {datetime.date(2026, 1, 5)}


@pytest.mark.django_db
def test_the_clock_is_injected_rather_than_read_from_the_wall(household):
    """A clock years away proves nothing is reading the real current time."""
    moment = datetime.datetime(2030, 6, 30, 12, 0, tzinfo=ZoneInfo("Pacific/Auckland"))
    load("Rose Cottage", clock=pinned_clock(moment))
    start_dates = set(household.chore_definitions.values_list("start_date", flat=True))
    assert start_dates == {datetime.date(2030, 6, 30)}


@pytest.mark.django_db
def test_start_date_is_never_the_epoch_or_a_hardcoded_date(household):
    load("Rose Cottage")
    assert datetime.date(1970, 1, 1) not in set(
        household.chore_definitions.values_list("start_date", flat=True)
    )


# The report on stdout


@pytest.mark.django_db
def test_the_report_says_how_many_were_created(household):
    output = load("Rose Cottage")
    assert f"{len(CHORE_LIBRARY)} chore definition(s) created" in output
    assert "0 already present" in output


@pytest.mark.django_db
def test_the_report_says_how_many_were_already_present(household):
    load("Rose Cottage")
    output = load("Rose Cottage")
    assert "0 chore definition(s) created" in output
    assert f"{len(CHORE_LIBRARY)} already present" in output


# --dry-run


@pytest.mark.django_db
def test_dry_run_writes_nothing(household):
    load("Rose Cottage", dry_run=True)
    assert household.chore_definitions.count() == 0


@pytest.mark.django_db
def test_dry_run_prints_the_same_report(household):
    dry = load("Rose Cottage", dry_run=True)
    wet = load("Rose Cottage")
    assert f"{len(CHORE_LIBRARY)} chore definition(s) created" in dry
    for entry in CHORE_LIBRARY:
        assert f"created  {entry['name']}" in dry
    assert "Dry run: nothing was written." in dry
    assert "Dry run" not in wet


@pytest.mark.django_db
def test_dry_run_still_refuses_an_unknown_household(household):
    with pytest.raises(CommandError):
        load("Nowhere House", dry_run=True)
