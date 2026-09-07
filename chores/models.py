from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
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
