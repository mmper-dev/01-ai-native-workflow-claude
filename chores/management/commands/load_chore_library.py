"""Load the standard chore library into one household (issue #35).

The library itself lives in `chores/management/chore_library.py`; this module
only resolves the household, works out today's date in that household's own
calendar, and writes the rows.

Two things here are load-bearing and easy to undo by accident:

* Every row goes through `full_clean()` before it is saved. Issue #47 records
  that `assignment_mode` and `recurrence` have no database-level guard, so a
  typo in the library data reaches the table intact on any path that skips
  validation. This command is the only writer of the library, so this is the
  guard.
* The whole load is one transaction, so a bad entry half way down leaves the
  household exactly as it was rather than half seeded.
"""

import datetime
from collections.abc import Callable, Iterable, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chores.management.chore_library import CHORE_LIBRARY
from chores.models import ChoreDefinition, Household


def _utc_now() -> datetime.datetime:
    """The default clock. A module-level function so tests can swap it out.

    `django.utils.timezone.now` would do, but naming it here keeps the
    injection point obvious and the command free of a timezone import that
    reads like the household's timezone.
    """
    return datetime.datetime.now(datetime.UTC)


class Command(BaseCommand):
    help = (
        "Load the standard library of household chores into one household, "
        "named by its Household.name. "
        "Running the command twice creates nothing the second time: an entry "
        "is skipped when the household already holds a chore definition with "
        "exactly that name. Matching is exact and case-sensitive, so a "
        "household that has renamed 'Dishes' to 'Washing up' gets 'Dishes' "
        "added back as a new chore on the next run, and a household holding "
        "'dishes' gets 'Dishes' alongside it rather than instead of it."
    )

    def __init__(
        self,
        *args,
        clock: Callable[[], datetime.datetime] | None = None,
        library: Iterable[Mapping[str, object]] | None = None,
        **kwargs,
    ) -> None:
        """Accept an injected clock and an injected library.

        The clock is an AGENTS.md rule: time-dependent logic must not read the
        current time directly, so `start_date` stays testable. The library is
        injectable so a test can point the command at deliberately broken data
        without patching module state.
        """
        super().__init__(*args, **kwargs)
        self.clock = clock or _utc_now
        self.library = CHORE_LIBRARY if library is None else tuple(library)

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "household",
            # Optional to argparse, required to us: a missing name should list
            # the households that do exist rather than print argparse's usage.
            nargs="?",
            default=None,
            help="The Household.name to load into. Matched exactly.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the same report and write nothing.",
        )

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        household = self._resolve_household(options["household"])
        today = self._today_in(household)

        created: list[str] = []
        present: list[str] = []

        # One transaction for the whole load: a failure part way down rolls the
        # earlier rows back, so the household is never half seeded.
        with transaction.atomic():
            seen = set(household.chore_definitions.values_list("name", flat=True))
            for entry in self.library:
                definition = self._build(household, entry, today)
                if definition.name in seen:
                    present.append(definition.name)
                    continue
                self._validate(definition)
                if not dry_run:
                    definition.save()
                seen.add(definition.name)
                created.append(definition.name)
            if dry_run:
                # Nothing was saved above, but rolling back as well means a
                # future edit to this loop cannot make --dry-run write.
                transaction.set_rollback(True)

        self._report(household, today, created, present, dry_run)

    # Resolving the household

    def _resolve_household(self, name: str | None) -> Household:
        if name is None or not name.strip():
            raise CommandError(
                f"Name the household to load the chore library into.\n{self._known_households()}"
            )

        wanted = name.strip()
        matches = list(Household.objects.filter(name=wanted).order_by("pk"))

        if not matches:
            raise CommandError(f"No household is named {wanted!r}.\n{self._known_households()}")
        if len(matches) > 1:
            # Household.name is not unique -- issue #2 put no constraint on it.
            # Picking the first would seed an arbitrary one of them.
            listed = "\n".join(f"  id={h.pk}  {h.name!r}  ({h.timezone})" for h in matches)
            raise CommandError(
                f"{len(matches)} households are named {wanted!r}, so this is ambiguous. "
                f"Nothing was written. The matches are:\n{listed}"
            )
        return matches[0]

    def _known_households(self) -> str:
        households = list(Household.objects.order_by("name", "pk"))
        if not households:
            return "No households exist yet."
        listed = "\n".join(f"  {h.name!r}  (id={h.pk})" for h in households)
        return f"Households that exist:\n{listed}"

    # Today, in the household's own calendar

    def _today_in(self, household: Household) -> datetime.date:
        """The current date where the household lives, not where the server is.

        Issue #6 anchors its recurrence grid on `start_date` and skips grid
        points before the definition existed, so a date that is a day out here
        produces either a flood of occurrences or a gap.
        """
        try:
            tz = ZoneInfo(household.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise CommandError(
                f"Household {household.name!r} (id={household.pk}) has an unknown "
                f"timezone {household.timezone!r}, so today's date cannot be worked out."
            ) from exc

        now = self.clock()
        if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            # A naive clock is read as UTC rather than as local server time, so
            # an injected one behaves the same wherever the tests run.
            now = now.replace(tzinfo=datetime.UTC)
        return now.astimezone(tz).date()

    # Building and validating one row

    def _build(
        self, household: Household, entry: Mapping[str, object], today: datetime.date
    ) -> ChoreDefinition:
        definition = ChoreDefinition(
            household=household,
            start_date=today,
            # fixed_member stays null: issue #3 constrains any mode other than
            # 'assign' to name no fixed member, and the library knows nothing
            # about who is in the household.
            fixed_member=None,
            **entry,
        )
        # save() and clean() both strip, so match idempotency against the name
        # as it would be stored rather than as it is written in the library.
        definition.name = (definition.name or "").strip()
        return definition

    def _validate(self, definition: ChoreDefinition) -> None:
        try:
            definition.full_clean()
        except ValidationError as exc:
            problems = "; ".join(
                f"{field}: {' '.join(messages)}"
                for field, messages in sorted(exc.message_dict.items())
            )
            raise CommandError(
                f"The chore library entry {definition.name!r} is not valid, so nothing "
                f"was written: {problems}"
            ) from exc

    # Reporting

    def _report(
        self,
        household: Household,
        today: datetime.date,
        created: list[str],
        present: list[str],
        dry_run: bool,
    ) -> None:
        self.stdout.write(f"Household {household.name!r} (id={household.pk}, {household.timezone})")
        self.stdout.write(f"Start date for new chores: {today.isoformat()}")
        for name in created:
            self.stdout.write(f"  created  {name}")
        for name in present:
            self.stdout.write(f"  present  {name}")
        summary = (
            f"{len(created)} chore definition(s) created, "
            f"{len(present)} already present, "
            f"{len(self.library)} in the library."
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: nothing was written. {summary}"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
