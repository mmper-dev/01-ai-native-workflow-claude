"""Tests for issue #13 -- Django admin registration.

One test per acceptance criterion on the issue, in the order they are listed
there, as the other test modules do. Everything goes through the test client
wherever it can: the criterion is that a superuser can click the app into
existence, and only a real request proves that.
"""

import datetime
import re

import pytest
from django.contrib import admin
from django.contrib.admin.sites import site
from django.db import connection
from django.forms import CheckboxSelectMultiple
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from chores.admin import ChoreOccurrenceAdmin, MembershipInline
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

START = "2026-01-05"
DUE_DATE = "2026-01-05"
DUE_TIME = "18:00:00"
DUE = datetime.datetime(2026, 1, 5, 18, 0, tzinfo=datetime.UTC)

# Every model the issue says must be reachable, by model_name.
REGISTERED = ["user", "household", "membership", "choredefinition", "choreoccurrence"]

READ_ONLY_OCCURRENCE_FIELDS = {"estimated_minutes", "difficulty", "state", "overdue_at"}


# Fixtures


@pytest.fixture(autouse=True)
def utc(settings):
    """Pin the display timezone, so a posted due time is the instant asserted."""
    settings.TIME_ZONE = "UTC"


@pytest.fixture(autouse=True)
def unhashed_static(settings):
    """Serve admin CSS without a staticfiles manifest.

    The project stores static files with WhiteNoise's manifest backend, which
    skips hashing while `DEBUG` is on -- so `runserver` is fine -- but the test
    runner forces `DEBUG=False`, and every admin template starts with
    `{% static 'admin/css/base.css' %}`. Without this, these tests would only
    be asserting that nobody has run `collectstatic`.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def superuser(db):
    """A superuser, not a bare `is_staff` user.

    A staff user with no model permissions gets 403 on every changelist, which
    would make the tests below pass for entirely the wrong reason.
    """
    return User.objects.create_superuser(
        username="root", email="root@example.com", password="pw-for-tests"
    )


@pytest.fixture
def su(client, superuser):
    client.force_login(superuser)
    return client


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
        start_date=datetime.date(2026, 1, 5),
        recurrence=Recurrence.ONE_OFF,
    )


@pytest.fixture
def occurrence(db, definition):
    return ChoreOccurrence.objects.create(definition=definition, due_at=DUE)


# Helpers


def url(model_name, view, *args):
    return reverse(f"admin:chores_{model_name}_{view}", args=args)


def model_admin_for(model_name):
    return next(
        value for key, value in site._registry.items() if key._meta.model_name == model_name
    )


def errors(response):
    """Every form error on an admin add/change page, for readable assertions."""
    context = getattr(response, "context", None)
    if not context:
        return {}
    found = {}
    try:
        form_errors = context["adminform"].form.errors
    except KeyError:
        form_errors = {}
    for key, value in form_errors.items():
        found[key] = [str(message) for message in value]
    for inline in context.get("inline_admin_formsets") or []:
        for form in inline.formset.forms:
            for key, value in form.errors.items():
                found.setdefault(f"inline:{key}", [str(message) for message in value])
    return found


def user_post(username, email, **overrides):
    data = {
        "username": username,
        "email": email,
        "usable_password": "true",
        "password1": "correct-horse-42",
        "password2": "correct-horse-42",
    }
    data.update(overrides)
    return data


def household_post(name="Rose Cottage", *, memberships=(), **overrides):
    data = {
        "name": name,
        "timezone": "UTC",
        "memberships-TOTAL_FORMS": str(len(memberships)),
        "memberships-INITIAL_FORMS": "0",
        "memberships-MIN_NUM_FORMS": "0",
        "memberships-MAX_NUM_FORMS": "1000",
    }
    for index, (user, roles) in enumerate(memberships):
        data[f"memberships-{index}-id"] = ""
        data[f"memberships-{index}-user"] = str(user.pk)
        data[f"memberships-{index}-roles"] = list(roles)
    data.update(overrides)
    return data


def definition_post(household, **overrides):
    data = {
        "household": household.pk,
        "name": "Dishes",
        "estimated_minutes": "15",
        "difficulty": "2",
        "assignment_mode": AssignmentMode.ROTATE,
        "fixed_member": "",
        "start_date": START,
        "recurrence": Recurrence.ONE_OFF,
        "interval_days": "",
    }
    data.update(overrides)
    return data


def occurrence_post(definition, **overrides):
    data = {
        "definition": definition.pk,
        "assignee": "",
        "due_at_0": DUE_DATE,
        "due_at_1": DUE_TIME,
    }
    data.update(overrides)
    return data


# Registration and changelists


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", REGISTERED)
def test_every_model_is_registered(model_name):
    registered = {model._meta.model_name for model in site._registry}
    assert model_name in registered


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", REGISTERED)
def test_every_changelist_loads_for_a_superuser(su, model_name):
    assert su.get(url(model_name, "changelist")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("model_name", REGISTERED)
def test_every_add_form_loads_for_a_superuser(su, model_name):
    assert su.get(url(model_name, "add")).status_code == 200


@pytest.mark.django_db
def test_the_admin_index_links_to_every_model(su):
    response = su.get(reverse("admin:index"))
    assert response.status_code == 200
    body = response.content.decode()
    for model_name in REGISTERED:
        assert url(model_name, "changelist") in body


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        ("household", {"name", "timezone"}),
        ("membership", {"user", "household", "roles"}),
        (
            "choredefinition",
            {
                "name",
                "household",
                "assignment_mode",
                "recurrence",
                "estimated_minutes",
                "difficulty",
                "start_date",
            },
        ),
        ("choreoccurrence", {"definition", "household", "assignee", "due_at", "state"}),
    ],
)
def test_each_changelist_displays_the_columns_the_issue_names(model_name, expected):
    assert expected <= set(model_admin_for(model_name).list_display)


@pytest.mark.django_db
def test_the_occurrence_changelist_shows_an_overdue_yes_no_column(occurrence):
    """A boolean column, not the raw `overdue_at` timestamp."""
    model_admin = site._registry[ChoreOccurrence]
    assert "is_overdue" in model_admin.list_display
    assert model_admin.is_overdue.boolean is True
    assert model_admin.is_overdue(occurrence) is False
    occurrence.mark_overdue(now=DUE + datetime.timedelta(days=1))
    assert model_admin.is_overdue(occurrence) is True


@pytest.mark.django_db
def test_definitions_can_be_filtered_by_household(su, household, other_household, definition):
    ChoreDefinition.objects.create(
        household=other_household,
        name="Sand",
        estimated_minutes=5,
        difficulty=1,
        assignment_mode=AssignmentMode.CLAIM,
        start_date=datetime.date(2026, 1, 5),
    )
    response = su.get(url("choredefinition", "changelist"), {"household__id__exact": household.pk})
    assert response.status_code == 200
    assert [obj.pk for obj in response.context["cl"].queryset] == [definition.pk]


@pytest.mark.django_db
def test_memberships_can_be_filtered_by_household(su, household, member):
    assert "household" in model_admin_for("membership").list_filter
    response = su.get(url("membership", "changelist"), {"household__id__exact": household.pk})
    assert response.status_code == 200
    assert [obj.user_id for obj in response.context["cl"].queryset] == [member.pk]


@pytest.mark.django_db
def test_definitions_can_be_filtered_by_assignment_mode_and_recurrence(su, definition):
    assert {"assignment_mode", "recurrence"} <= set(model_admin_for("choredefinition").list_filter)
    response = su.get(
        url("choredefinition", "changelist"), {"assignment_mode__exact": AssignmentMode.ASSIGN}
    )
    assert response.status_code == 200
    assert list(response.context["cl"].queryset) == []


@pytest.mark.django_db
def test_occurrences_can_be_filtered_by_state(su, definition, occurrence):
    assert "state" in model_admin_for("choreoccurrence").list_filter
    response = su.get(url("choreoccurrence", "changelist"), {"state__exact": "done"})
    assert response.status_code == 200
    assert list(response.context["cl"].queryset) == []


@pytest.mark.django_db
def test_search_finds_a_household_by_name(su, household, other_household):
    response = su.get(url("household", "changelist"), {"q": "Rose"})
    assert [obj.pk for obj in response.context["cl"].queryset] == [household.pk]


@pytest.mark.django_db
def test_search_finds_a_definition_by_name(su, definition):
    found = su.get(url("choredefinition", "changelist"), {"q": "Dish"})
    assert [obj.pk for obj in found.context["cl"].queryset] == [definition.pk]
    missing = su.get(url("choredefinition", "changelist"), {"q": "Nope"})
    assert list(missing.context["cl"].queryset) == []


# The occurrence reaches its household through the definition


@pytest.mark.django_db
def test_the_occurrence_admin_reaches_the_household_through_the_definition(occurrence, household):
    """#4 leaves `household` off the occurrence deliberately; nothing here adds it."""
    assert "household" not in {field.name for field in ChoreOccurrence._meta.get_fields()}
    model_admin = site._registry[ChoreOccurrence]
    assert model_admin.household(occurrence) == household
    assert any(
        isinstance(entry, tuple) and entry[0] == "definition__household"
        for entry in model_admin.list_filter
    )


@pytest.mark.django_db
def test_the_occurrence_changelist_filters_by_the_definitions_household(
    su, household, other_household, occurrence
):
    elsewhere = ChoreDefinition.objects.create(
        household=other_household,
        name="Sand",
        estimated_minutes=5,
        difficulty=1,
        assignment_mode=AssignmentMode.CLAIM,
        start_date=datetime.date(2026, 1, 5),
    )
    ChoreOccurrence.objects.create(definition=elsewhere, due_at=DUE)
    response = su.get(
        url("choreoccurrence", "changelist"),
        {"definition__household__id__exact": household.pk},
    )
    assert response.status_code == 200
    assert [obj.pk for obj in response.context["cl"].queryset] == [occurrence.pk]


# Overdue is filtered as a flag, not as a date


@pytest.mark.django_db
def test_overdue_is_filtered_as_a_flag_and_the_rows_are_still_pending(su, definition, occurrence):
    later = ChoreOccurrence.objects.create(
        definition=definition, due_at=DUE + datetime.timedelta(days=1)
    )
    later.mark_overdue(now=DUE + datetime.timedelta(days=2))

    model_admin = site._registry[ChoreOccurrence]
    assert ("overdue_at", admin.EmptyFieldListFilter) in model_admin.list_filter

    response = su.get(url("choreoccurrence", "changelist"), {"overdue_at__isempty": "0"})
    assert response.status_code == 200
    rows = list(response.context["cl"].queryset)
    assert [obj.pk for obj in rows] == [later.pk]
    # Overdue is a flag, not a state: the row is still pending and still owed.
    assert rows[0].state == OccurrenceState.PENDING

    not_overdue = su.get(url("choreoccurrence", "changelist"), {"overdue_at__isempty": "1"})
    assert [obj.pk for obj in not_overdue.context["cl"].queryset] == [occurrence.pk]


# A household and its members, start to finish


@pytest.mark.django_db
def test_membership_is_a_tabular_inline_on_household():
    assert MembershipInline in site._registry[Household].inlines
    assert issubclass(MembershipInline, admin.TabularInline)
    assert MembershipInline.model is Membership


@pytest.mark.django_db
def test_membership_is_also_registered_in_its_own_right(su):
    assert Membership in site._registry
    assert su.get(url("membership", "changelist")).status_code == 200


@pytest.mark.django_db
def test_the_household_change_page_renders_the_membership_inline(su, household, member):
    response = su.get(url("household", "change", household.pk))
    assert response.status_code == 200
    formsets = response.context["inline_admin_formsets"]
    assert any(entry.formset.model is Membership for entry in formsets)


@pytest.mark.django_db
def test_a_household_and_both_its_members_are_created_from_one_screen(su, member, outsider):
    response = su.post(
        url("household", "add"),
        household_post(
            "Lake Cabin",
            memberships=[(member, ["admin", "user"]), (outsider, ["user"])],
        ),
    )
    assert response.status_code == 302, errors(response)
    created = Household.objects.get(name="Lake Cabin")
    assert created.memberships.count() == 2
    assert created.memberships.get(user=member).roles == ["admin", "user"]
    assert created.memberships.get(user=outsider).roles == ["user"]


# Roles are ticked, not typed


@pytest.mark.django_db
def test_roles_uses_a_checkbox_widget_rather_than_a_json_textarea(su):
    response = su.get(url("membership", "add"))
    field = response.context["adminform"].form.fields["roles"]
    assert isinstance(field.widget, CheckboxSelectMultiple)

    body = response.content.decode()
    assert '<textarea name="roles"' not in body
    for role in ("admin", "user"):
        pattern = rf'<input[^>]*type="checkbox"[^>]*name="roles"[^>]*value="{role}"'
        assert re.search(pattern, body), f"no checkbox for {role!r}"


@pytest.mark.django_db
def test_the_roles_widget_offers_exactly_the_two_role_choices(su):
    response = su.get(url("membership", "add"))
    field = response.context["adminform"].form.fields["roles"]
    assert [(value, str(label)) for value, label in field.choices] == Membership.ROLE_CHOICES


@pytest.mark.django_db
def test_ticking_no_role_saves_an_empty_list(su, member, household):
    Membership.objects.all().delete()
    response = su.post(url("membership", "add"), {"user": member.pk, "household": household.pk})
    assert response.status_code == 302, errors(response)
    assert Membership.objects.get().roles == []


@pytest.mark.django_db
def test_ticking_both_roles_saves_both(su, member, household):
    Membership.objects.all().delete()
    response = su.post(
        url("membership", "add"),
        {"user": member.pk, "household": household.pk, "roles": ["admin", "user"]},
    )
    assert response.status_code == 302, errors(response)
    assert Membership.objects.get().roles == ["admin", "user"]


@pytest.mark.django_db
def test_reopening_a_membership_shows_the_same_boxes_ticked(su, member, household):
    membership = Membership.objects.get(user=member, household=household)
    membership.roles = ["admin"]
    membership.save()

    response = su.get(url("membership", "change", membership.pk))
    assert response.status_code == 200
    assert response.context["adminform"].form["roles"].value() == ["admin"]

    ticked = re.findall(r'<input[^>]*name="roles"[^>]*checked[^>]*>', response.content.decode())
    assert len(ticked) == 1
    assert 'value="admin"' in ticked[0]


@pytest.mark.django_db
def test_an_unknown_role_cannot_be_typed_in(su, member, household):
    """The field only accepts ROLE_CHOICES, so `["wizard"]` is a form error."""
    Membership.objects.all().delete()
    response = su.post(
        url("membership", "add"),
        {"user": member.pk, "household": household.pk, "roles": ["wizard"]},
    )
    assert response.status_code == 200
    assert "roles" in errors(response)
    assert not Membership.objects.exists()


@pytest.mark.django_db
def test_the_roles_widget_is_admin_only_and_the_model_is_unchanged():
    field = Membership._meta.get_field("roles")
    assert field.get_internal_type() == "JSONField"
    assert not field.choices


# A second user can be created through the admin


@pytest.mark.django_db
def test_the_user_add_form_asks_for_email(su):
    response = su.get(url("user", "add"))
    assert response.status_code == 200
    assert "email" in response.context["adminform"].form.fields


@pytest.mark.django_db
def test_two_users_can_be_created_in_a_row_through_the_admin(su):
    """The regression the issue names: the second one used to 500."""
    before = User.objects.count()

    first = su.post(url("user", "add"), user_post("ana", "ana@example.com"))
    assert first.status_code == 302, errors(first)

    second = su.post(url("user", "add"), user_post("ben", "ben@example.com"))
    assert second.status_code == 302, errors(second)

    assert User.objects.count() == before + 2
    assert User.objects.get(username="ana").email == "ana@example.com"
    assert User.objects.get(username="ben").email == "ben@example.com"


@pytest.mark.django_db
def test_a_duplicate_email_is_a_form_error_not_a_500(su):
    su.post(url("user", "add"), user_post("ana", "ana@example.com"))
    response = su.post(url("user", "add"), user_post("ben", "ana@example.com"))
    assert response.status_code == 200
    assert "email" in errors(response)
    assert not User.objects.filter(username="ben").exists()


@pytest.mark.django_db
def test_a_missing_email_is_a_form_error(su):
    response = su.post(url("user", "add"), user_post("ana", ""))
    assert response.status_code == 200
    assert "email" in errors(response)


# The whole walkthrough, on an empty database


@pytest.mark.django_db
def test_a_superuser_can_build_a_household_end_to_end(su):
    """Two users, a household with both as members, a chore, an occurrence."""
    assert not Household.objects.exists()

    for username, email in [("ana", "ana@example.com"), ("ben", "ben@example.com")]:
        response = su.post(url("user", "add"), user_post(username, email))
        assert response.status_code == 302, errors(response)
    ana = User.objects.get(username="ana")
    ben = User.objects.get(username="ben")

    response = su.post(
        url("household", "add"),
        household_post("Rose Cottage", memberships=[(ana, ["admin"]), (ben, ["user"])]),
    )
    assert response.status_code == 302, errors(response)
    household = Household.objects.get(name="Rose Cottage")
    assert household.memberships.count() == 2

    response = su.post(url("choredefinition", "add"), definition_post(household))
    assert response.status_code == 302, errors(response)
    definition = ChoreDefinition.objects.get(household=household, name="Dishes")

    response = su.post(url("choreoccurrence", "add"), occurrence_post(definition, assignee=ana.pk))
    assert response.status_code == 302, errors(response)

    created = ChoreOccurrence.objects.get(definition=definition)
    assert created.assignee == ana
    assert created.state == OccurrenceState.PENDING
    assert (created.estimated_minutes, created.difficulty) == (15, 2)


# The occurrence must not become a back door


@pytest.mark.django_db
def test_the_effort_state_and_overdue_fields_are_read_only(occurrence):
    model_admin = site._registry[ChoreOccurrence]
    assert READ_ONLY_OCCURRENCE_FIELDS <= set(model_admin.get_readonly_fields(None))
    assert READ_ONLY_OCCURRENCE_FIELDS <= set(model_admin.get_readonly_fields(None, occurrence))


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["add", "change"])
def test_the_read_only_fields_are_absent_from_both_forms(su, occurrence, view):
    args = [] if view == "add" else [occurrence.pk]
    response = su.get(url("choreoccurrence", view, *args))
    assert response.status_code == 200
    fields = set(response.context["adminform"].form.fields)
    assert fields.isdisjoint(READ_ONLY_OCCURRENCE_FIELDS)


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["add", "change"])
def test_the_frozen_values_are_still_on_screen(su, occurrence, view):
    """`readonly_fields`, not `exclude`: you can see them, you cannot edit them."""
    args = [] if view == "add" else [occurrence.pk]
    response = su.get(url("choreoccurrence", view, *args))
    shown = set()
    for fieldset in response.context["adminform"]:
        for line in fieldset:
            shown.update(line.fields)
    assert READ_ONLY_OCCURRENCE_FIELDS <= shown


@pytest.mark.django_db
def test_creating_an_occurrence_through_the_admin_freezes_the_effort_values(su, definition):
    response = su.post(url("choreoccurrence", "add"), occurrence_post(definition))
    assert response.status_code == 302, errors(response)
    created = ChoreOccurrence.objects.get(definition=definition)
    assert created.estimated_minutes == definition.estimated_minutes == 15
    assert created.difficulty == definition.difficulty == 2


@pytest.mark.django_db
def test_re_saving_an_occurrence_through_the_admin_does_not_re_copy(su, definition, occurrence):
    definition.estimated_minutes = 999
    definition.difficulty = 5
    definition.save()

    response = su.post(url("choreoccurrence", "change", occurrence.pk), occurrence_post(definition))
    assert response.status_code == 302, errors(response)

    occurrence.refresh_from_db()
    assert occurrence.estimated_minutes == 15
    assert occurrence.difficulty == 2


@pytest.mark.django_db
def test_posting_effort_values_anyway_changes_nothing(su, definition, occurrence):
    response = su.post(
        url("choreoccurrence", "change", occurrence.pk),
        occurrence_post(definition, estimated_minutes="999", difficulty="5"),
    )
    assert response.status_code == 302, errors(response)
    occurrence.refresh_from_db()
    assert (occurrence.estimated_minutes, occurrence.difficulty) == (15, 2)


@pytest.mark.django_db
def test_posting_state_and_overdue_at_anyway_changes_nothing(su, definition, occurrence):
    """#5's `mark_done` / `mark_overdue` are the only routes; the admin has none."""
    response = su.post(
        url("choreoccurrence", "change", occurrence.pk),
        occurrence_post(
            definition,
            state=OccurrenceState.DONE,
            overdue_at_0="2026-01-06",
            overdue_at_1="09:00:00",
        ),
    )
    assert response.status_code == 302, errors(response)
    occurrence.refresh_from_db()
    assert occurrence.state == OccurrenceState.PENDING
    assert occurrence.overdue_at is None


@pytest.mark.django_db
def test_the_admin_offers_no_lifecycle_or_effort_action(su):
    """#10, #12 and #23 own those, and each writes a record this screen cannot."""
    assert ChoreOccurrenceAdmin.actions in (None, [], ())
    response = su.get(url("choreoccurrence", "changelist"))
    available = set(site._registry[ChoreOccurrence].get_actions(response.wsgi_request))
    assert available <= {"delete_selected"}


@pytest.mark.django_db
def test_the_assignee_stays_editable(su, definition, occurrence, member):
    response = su.get(url("choreoccurrence", "change", occurrence.pk))
    assert "assignee" in response.context["adminform"].form.fields

    response = su.post(
        url("choreoccurrence", "change", occurrence.pk),
        occurrence_post(definition, assignee=member.pk),
    )
    assert response.status_code == 302, errors(response)
    occurrence.refresh_from_db()
    assert occurrence.assignee == member


# Model validation shows as a form error, never a 500


@pytest.mark.django_db
def test_assign_mode_without_a_fixed_member_is_a_form_error(su, household):
    response = su.post(
        url("choredefinition", "add"),
        definition_post(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=""),
    )
    assert response.status_code == 200
    assert "fixed_member" in errors(response)


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [AssignmentMode.ROTATE, AssignmentMode.CLAIM])
def test_a_non_assign_mode_with_a_fixed_member_is_a_form_error(su, household, member, mode):
    response = su.post(
        url("choredefinition", "add"),
        definition_post(household, assignment_mode=mode, fixed_member=member.pk),
    )
    assert response.status_code == 200
    assert "fixed_member" in errors(response)


@pytest.mark.django_db
def test_a_fixed_member_outside_the_household_is_a_form_error(su, household, outsider):
    """The dropdown lists every user, so this is reachable by clicking."""
    response = su.post(
        url("choredefinition", "add"),
        definition_post(household, assignment_mode=AssignmentMode.ASSIGN, fixed_member=outsider.pk),
    )
    assert response.status_code == 200
    assert "fixed_member" in errors(response)
    assert not ChoreDefinition.objects.exists()


@pytest.mark.django_db
def test_an_assignee_outside_the_definitions_household_is_a_form_error(
    su, definition, other_household, outsider
):
    Membership.objects.create(user=outsider, household=other_household)
    response = su.post(
        url("choreoccurrence", "add"), occurrence_post(definition, assignee=outsider.pk)
    )
    assert response.status_code == 200
    assert "assignee" in errors(response)
    assert not ChoreOccurrence.objects.exists()


@pytest.mark.django_db
def test_interval_recurrence_without_interval_days_is_a_form_error(su, household):
    response = su.post(
        url("choredefinition", "add"),
        definition_post(household, recurrence=Recurrence.INTERVAL, interval_days=""),
    )
    assert response.status_code == 200
    assert "interval_days" in errors(response)


@pytest.mark.django_db
def test_a_one_off_with_interval_days_is_a_form_error(su, household):
    response = su.post(
        url("choredefinition", "add"),
        definition_post(household, recurrence=Recurrence.ONE_OFF, interval_days="7"),
    )
    assert response.status_code == 200
    assert "interval_days" in errors(response)


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", "   "])
def test_a_blank_household_name_is_a_form_error(su, name):
    response = su.post(url("household", "add"), household_post(name))
    assert response.status_code == 200
    assert "name" in errors(response)
    assert not Household.objects.exists()


@pytest.mark.django_db
def test_an_unresolvable_timezone_is_a_form_error(su):
    response = su.post(url("household", "add"), household_post(timezone="Mars/Olympus"))
    assert response.status_code == 200
    assert "timezone" in errors(response)
    assert not Household.objects.exists()


@pytest.mark.django_db
def test_a_duplicate_definition_name_in_one_household_is_a_form_error(su, household, definition):
    response = su.post(url("choredefinition", "add"), definition_post(household, name="Dishes"))
    assert response.status_code == 200
    assert errors(response), "the duplicate reached the database instead of the form"
    assert ChoreDefinition.objects.filter(household=household, name="Dishes").count() == 1


@pytest.mark.django_db
def test_the_same_definition_name_in_another_household_is_fine(su, other_household, definition):
    response = su.post(
        url("choredefinition", "add"), definition_post(other_household, name="Dishes")
    )
    assert response.status_code == 302, errors(response)
    assert ChoreDefinition.objects.filter(name="Dishes").count() == 2


@pytest.mark.django_db
def test_a_duplicate_occurrence_due_at_is_a_form_error(su, definition, occurrence):
    response = su.post(url("choreoccurrence", "add"), occurrence_post(definition))
    assert response.status_code == 200
    assert errors(response), "the duplicate reached the database instead of the form"
    assert ChoreOccurrence.objects.filter(definition=definition).count() == 1


# Deletion is blocked by PROTECT, and shown as the protected-object page

PROTECTED_TARGETS = {
    "household": ("household", Household),
    "definition": ("choredefinition", ChoreDefinition),
    "user": ("user", User),
}


@pytest.fixture
def protected(request, household, member, definition):
    """An object with history behind it, plus its admin model_name."""
    ChoreOccurrence.objects.create(definition=definition, due_at=DUE)
    model_name, model = PROTECTED_TARGETS[request.param]
    obj = {"household": household, "definition": definition, "user": member}[request.param]
    return obj, model_name, model


@pytest.mark.django_db
@pytest.mark.parametrize("protected", list(PROTECTED_TARGETS), indirect=True)
def test_the_delete_view_shows_the_protected_page(su, protected):
    obj, model_name, model = protected
    response = su.get(url(model_name, "delete", obj.pk))
    assert response.status_code == 200
    assert response.context["protected"], "expected Django's protected-object page"
    assert model.objects.filter(pk=obj.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("protected", list(PROTECTED_TARGETS), indirect=True)
def test_the_delete_selected_action_shows_the_protected_page(su, protected):
    obj, model_name, model = protected
    response = su.post(
        url(model_name, "changelist"),
        {"action": "delete_selected", "_selected_action": [str(obj.pk)], "index": "0"},
    )
    assert response.status_code == 200
    assert response.context["protected"], "expected Django's protected-object page"
    assert model.objects.filter(pk=obj.pk).exists()


# Performance


@pytest.mark.django_db
def test_the_occurrence_changelist_does_not_n_plus_one(su, definition, member):
    """`list_select_related` covers the definition, its household and the assignee."""
    model_admin = site._registry[ChoreOccurrence]
    assert {"definition", "assignee"} <= set(model_admin.list_select_related)

    def queries_for(count):
        ChoreOccurrence.objects.all().delete()
        for day in range(count):
            ChoreOccurrence.objects.create(
                definition=definition,
                assignee=member,
                due_at=DUE + datetime.timedelta(days=day),
            )
        with CaptureQueriesContext(connection) as captured:
            response = su.get(url("choreoccurrence", "changelist"))
            assert response.status_code == 200
            assert response.content  # force the rows to render
        return len(captured)

    assert queries_for(1) == queries_for(6)
