from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    """Custom user, swapped in from migration zero so it can grow later.

    Household membership, skills, availability and the stretch-learning opt-in
    are deliberately NOT here -- they belong to a Membership model, because the
    plan scopes them per household rather than per person globally.
    """

    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


def default_timezone() -> str:
    """Read the project timezone at creation time rather than at import time.

    A callable keeps the default out of the migration as a frozen string, so
    changing TIME_ZONE changes what new households get.
    """
    return settings.TIME_ZONE


def validate_not_blank(value: str) -> None:
    """Reject a value that is empty once stripped.

    A field validator rather than model `clean()`, because `full_clean()` runs
    `clean_fields()` first -- stripping in `clean()` happens after the blank
    check has already passed a name of spaces.
    """
    if not (value or "").strip():
        raise ValidationError("This field cannot be blank.")


def validate_timezone(value: str) -> None:
    """Reject a timezone name zoneinfo cannot resolve.

    Not in the acceptance criteria, but a household carrying a nonsense
    timezone would not fail until task 6 tried to work out when a chore is
    due -- a long way from the form that accepted it.
    """
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"{value!r} is not a known timezone.") from exc


class Household(models.Model):
    """A group of people sharing a chore list."""

    name = models.CharField(max_length=200, validators=[validate_not_blank])
    timezone = models.CharField(
        max_length=64,
        default=default_timezone,
        validators=[validate_timezone],
        help_text="IANA timezone name. Due times are computed and displayed in it.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="household_name_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Strip before storing so a name of spaces becomes "" and is caught by
        # household_name_not_blank. Django does not strip model CharFields, and
        # a household called "   " renders as blank on every screen.
        self.name = (self.name or "").strip()
        return super().save(*args, **kwargs)

    def clean(self) -> None:
        self.name = (self.name or "").strip()
        super().clean()


class Membership(models.Model):
    """Joins a user to a household, carrying the roles they hold there.

    Roles are a set rather than an `is_admin` boolean because plan.md leaves
    open how the admin is chosen and whether there can be more than one.
    Answering that later must not need a data migration, so the roles live in
    a JSON list and adding a role is a change to ROLE_CHOICES alone.
    """

    ADMIN = "admin"
    USER = "user"
    ROLE_CHOICES = [(ADMIN, "Admin"), (USER, "User")]
    VALID_ROLES = frozenset(value for value, _label in ROLE_CHOICES)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    household = models.ForeignKey(
        Household,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    roles = models.JSONField(
        default=list,
        blank=True,
        help_text="Set of role names from ROLE_CHOICES. May be empty.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "household"],
                name="unique_membership_per_user_and_household",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.household}"

    def save(self, *args, **kwargs):
        # Normalise to a genuine set: deduplicated and ordered, so two
        # memberships holding the same roles compare equal and read the same.
        if isinstance(self.roles, list):
            self.roles = sorted(set(self.roles))
        return super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.roles, list):
            raise ValidationError({"roles": "Roles must be a list of role names."})
        unknown = sorted(set(self.roles) - self.VALID_ROLES)
        if unknown:
            raise ValidationError(
                {"roles": f"Unknown role(s): {', '.join(repr(role) for role in unknown)}."}
            )

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])

    @property
    def is_admin(self) -> bool:
        return self.has_role(self.ADMIN)


class AssignmentMode(models.TextChoices):
    """How a chore finds an owner. Task 42 renders these; task 7 branches on them.

    Module level rather than nested in ChoreDefinition, because a model's Meta
    is its own scope and cannot see names from the class body around it.
    """

    ROTATE = "rotate", "Rotate between members"
    ASSIGN = "assign", "Always the same person"
    CLAIM = "claim", "Anyone can claim it"


class Recurrence(models.TextChoices):
    """One-off, or a fixed interval in whole days. Richer rules are task 39."""

    ONE_OFF = "one_off", "One-off"
    INTERVAL = "interval", "Every N days"


MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


class ChoreDefinition(models.Model):
    """A reusable description of a piece of work a household repeats.

    The definition is the template; task 6 turns it into dated
    `ChoreOccurrence` rows. Effort lives here only as the value new
    occurrences are stamped with -- scoring always reads the occurrence's own
    copy, so editing a definition never rewrites a past score.
    """

    household = models.ForeignKey(
        Household,
        on_delete=models.PROTECT,
        related_name="chore_definitions",
    )
    name = models.CharField(max_length=200, validators=[validate_not_blank])
    estimated_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Rough duration in minutes. Must be at least 1.",
    )
    difficulty = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_DIFFICULTY), MaxValueValidator(MAX_DIFFICULTY)],
        help_text="How demanding the chore is, from 1 (easy) to 5 (hard).",
    )
    assignment_mode = models.CharField(
        max_length=16,
        choices=AssignmentMode.choices,
        help_text="How the chore finds an owner each time it comes round.",
    )
    fixed_member = models.ForeignKey(
        # A User rather than a Membership, matching ChoreOccurrence.assignee in
        # task 4: one way of naming a person, not two.
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fixed_chore_definitions",
        help_text="Required in 'assign' mode, and must be empty otherwise.",
    )
    start_date = models.DateField(
        # A local calendar date, not a datetime. Task 6 combines it with the
        # household timezone to get a UTC due_at; storing a datetime here would
        # give that conversion two timezones to reconcile.
        help_text="First date the chore is due, in the household's own calendar.",
    )
    recurrence = models.CharField(
        max_length=16,
        choices=Recurrence.choices,
        default=Recurrence.ONE_OFF,
        help_text="Whether the chore happens once or every interval_days days.",
    )
    interval_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Whole days between occurrences. Required for 'interval', empty otherwise.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="chore_definition_name_not_blank",
            ),
            models.UniqueConstraint(
                # Task 35 keys its seed idempotency on exactly this pair.
                # Matching is exact: "Dishes" and "dishes" are two chores.
                fields=["household", "name"],
                name="unique_chore_definition_name_per_household",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_minutes__gt=0),
                name="chore_definition_estimated_minutes_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(difficulty__gte=MIN_DIFFICULTY, difficulty__lte=MAX_DIFFICULTY),
                name="chore_definition_difficulty_in_range",
            ),
            models.CheckConstraint(
                condition=~models.Q(assignment_mode=AssignmentMode.ASSIGN)
                | models.Q(fixed_member__isnull=False),
                name="chore_definition_assign_mode_names_a_fixed_member",
            ),
            models.CheckConstraint(
                condition=models.Q(assignment_mode=AssignmentMode.ASSIGN)
                | models.Q(fixed_member__isnull=True),
                name="chore_definition_other_modes_have_no_fixed_member",
            ),
            models.CheckConstraint(
                condition=~models.Q(recurrence=Recurrence.INTERVAL)
                | models.Q(interval_days__isnull=False),
                name="chore_definition_interval_recurrence_has_interval_days",
            ),
            models.CheckConstraint(
                condition=~models.Q(recurrence=Recurrence.ONE_OFF)
                | models.Q(interval_days__isnull=True),
                name="chore_definition_one_off_recurrence_has_no_interval_days",
            ),
            models.CheckConstraint(
                # Zero would make task 6's generator return the same date forever.
                condition=models.Q(interval_days__isnull=True) | models.Q(interval_days__gt=0),
                name="chore_definition_interval_days_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Strip before storing, as Household.name does, so a name of spaces
        # becomes "" and chore_definition_name_not_blank catches it.
        self.name = (self.name or "").strip()
        return super().save(*args, **kwargs)

    def clean(self) -> None:
        self.name = (self.name or "").strip()
        super().clean()
        errors: dict[str, str] = {}

        if self.assignment_mode == AssignmentMode.ASSIGN and self.fixed_member_id is None:
            errors["fixed_member"] = "A chore assigned to one person must name that person."
        elif (
            self.assignment_mode in (AssignmentMode.ROTATE, AssignmentMode.CLAIM)
            and self.fixed_member_id is not None
        ):
            errors["fixed_member"] = (
                f"A chore in '{self.assignment_mode}' mode must not name a fixed member."
            )
        elif self.fixed_member_id is not None and self.household_id is not None:
            # Spans two tables, so no CheckConstraint can express it. Checked
            # when a definition is validated, not maintained forever -- task 7
            # covers a fixed member who has since left the household.
            in_household = Membership.objects.filter(
                user_id=self.fixed_member_id, household_id=self.household_id
            ).exists()
            if not in_household:
                errors["fixed_member"] = "The fixed member must belong to this household."

        if self.recurrence == Recurrence.INTERVAL and self.interval_days is None:
            errors["interval_days"] = "A repeating chore must say how many days apart."
        elif self.recurrence == Recurrence.ONE_OFF and self.interval_days is not None:
            errors["interval_days"] = "A one-off chore must not have an interval."

        if errors:
            raise ValidationError(errors)
