"""Django admin registration for issue #13.

Until #8 and #9 land there is no other usable surface: the admin is how a
household, its members, its chores and their occurrences come into existence at
all. So this is a working screen rather than a debugging convenience, and the
two places stock Django would get it wrong are fixed here:

* `UserAdmin.add_fieldsets` omits `email`, and `User.email` is `unique=True`
  with a `""` default -- so the *second* user created through the admin used to
  die with an `IntegrityError` 500 instead of a form error. The add form asks
  for it.
* `Membership.roles` is a `JSONField`, not a many-to-many, so the stock widget
  is a raw JSON textarea that invites `["wizard"]`. It gets checkboxes instead.

Everything here is admin-only: no model changes, no migrations.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    ChoreDefinition,
    ChoreOccurrence,
    Household,
    Membership,
    User,
)


@admin.register(User)
class ChoresUserAdmin(UserAdmin):
    """Stock `UserAdmin`, plus `email` on the add form.

    `User.email` is `unique=True` and defaults to `""`. Django's
    `add_fieldsets` does not list it, and a field absent from the form is
    excluded from the form's uniqueness check too -- so the first user created
    in the admin silently got `email=""` and the second one hit the unique
    index as a 500. Asking for it turns that into an ordinary required-field
    and already-exists error.
    """

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "usable_password", "password1", "password2"),
            },
        ),
    )


class MembershipRolesField(forms.MultipleChoiceField):
    """`Membership.roles` as checkboxes, for the admin only.

    The model stores a JSON list of role names, which the stock admin renders
    as a textarea containing raw JSON. This is a form field, not a model
    change: `MultipleChoiceField` cleans to a plain list of strings, which is
    exactly what the JSONField wants, and `Membership.clean()` still rejects
    anything outside `ROLE_CHOICES` on the paths that do not come through here.
    """

    widget = forms.CheckboxSelectMultiple

    def __init__(self, **kwargs):
        kwargs.setdefault("choices", Membership.ROLE_CHOICES)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def clean(self, value):
        # Sorted and deduplicated, matching what Membership.save() stores, so
        # the value the form validated is the value that lands in the column.
        return sorted(set(super().clean(value)))


class MembershipForm(forms.ModelForm):
    roles = MembershipRolesField(
        label="Roles",
        help_text="Tick the roles this person holds in this household. None is allowed.",
    )

    class Meta:
        model = Membership
        fields = ["user", "household", "roles"]


class MembershipInline(admin.TabularInline):
    """Members edited on the household screen, rather than on a third page.

    `Membership` stays registered in its own right as well -- a membership is
    reachable from the user's side too.
    """

    model = Membership
    form = MembershipForm
    fields = ("user", "roles")
    extra = 1


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "timezone")
    search_fields = ("name",)
    list_filter = ("timezone",)
    ordering = ("name",)
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    form = MembershipForm
    list_display = ("user", "household", "roles")
    list_filter = ("household",)
    list_select_related = ("user", "household")
    search_fields = ("user__username", "user__email", "household__name")
    ordering = ("household__name", "user__username")


@admin.register(ChoreDefinition)
class ChoreDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "household",
        "assignment_mode",
        "recurrence",
        "estimated_minutes",
        "difficulty",
        "start_date",
    )
    list_filter = ("household", "assignment_mode", "recurrence")
    list_select_related = ("household",)
    search_fields = ("name", "household__name")
    ordering = ("household__name", "name")


@admin.register(ChoreOccurrence)
class ChoreOccurrenceAdmin(admin.ModelAdmin):
    """The occurrence screen, deliberately narrower than the model.

    `estimated_minutes` and `difficulty` are frozen from the definition when
    the row is created (#4) and are what scoring reads. Editing them here would
    move somebody's score with nothing recorded about who did it, which is the
    thing plan.md relies on append-only history to make visible -- #23 is the
    route, and it writes a feed entry. `state` and `overdue_at` are read-only
    for the same kind of reason: #5's `mark_done()` and `mark_overdue()` guard
    the lifecycle and raise `IllegalTransition`, and a freely editable `state`
    makes that guard worthless. The consequence is intended: nothing here can
    complete an occurrence or flag it late.

    `assignee` stays editable. With #7 and #11 unbuilt this is the only way
    anyone gets assigned anything, and "nothing reassigns an overdue chore
    automatically" is a rule about automation, not about a person acting.
    """

    list_display = (
        "definition",
        "household",
        "assignee",
        "due_at",
        "state",
        "is_overdue",
    )
    list_filter = (
        ("definition__household", admin.RelatedOnlyFieldListFilter),
        "state",
        # A plain entry for `overdue_at` would give a date-range picker, which
        # is not the question anyone asks of a flag. This filters set/not set.
        ("overdue_at", admin.EmptyFieldListFilter),
    )
    # The household is reached through the definition -- #4 leaves the field
    # off the occurrence deliberately, so the two cannot disagree.
    list_select_related = ("definition", "definition__household", "assignee")
    search_fields = ("definition__name", "definition__household__name")
    ordering = ("due_at",)
    # Read-only on the add form as well as the change form, so the frozen
    # values are on screen without being a back door. On add they arrive at
    # full_clean() as None and #4 fills them from the definition; on a re-save
    # `_state.adding` is False, so nothing is re-copied.
    readonly_fields = ("estimated_minutes", "difficulty", "state", "overdue_at")

    @admin.display(description="Household", ordering="definition__household__name")
    def household(self, obj: ChoreOccurrence) -> Household:
        return obj.definition.household

    @admin.display(description="Overdue", boolean=True, ordering="overdue_at")
    def is_overdue(self, obj: ChoreOccurrence) -> bool:
        return obj.overdue_at is not None
