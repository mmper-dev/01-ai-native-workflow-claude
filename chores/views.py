import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import Household, Membership


def format_household_date(household: Household, now: datetime.datetime) -> str:
    """Render `now` as "Sunday 7 September" in the household's own timezone.

    The clock is an argument rather than a `timezone.now()` call inside
    (AGENTS.md), so a test can pin the date and assert the string. The
    household's `timezone` field decides which day it is, not the server's
    TIME_ZONE -- a household in Auckland is a day ahead of a UTC server for
    twelve hours of every day.
    """
    local = now.astimezone(ZoneInfo(household.timezone))
    # `local.day` rather than %d, because %-d is not portable to Windows and a
    # leading zero is not how a date is read aloud.
    return f"{local:%A} {local.day} {local:%B}"


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """What the household owes right now. #9 fills the list in.

    An account with no membership is a normal case, not an error: signing up
    creates a user and nothing else, and an admin has to add the membership.
    An account with more than one membership takes the lowest pk, so the page
    is deterministic until #43 lets a person choose.
    """
    membership = (
        Membership.objects.filter(user=request.user)
        .select_related("household")
        .order_by("pk")
        .first()
    )
    household = membership.household if membership else None
    context: dict[str, object] = {"household": household}
    if household is not None:
        context["today"] = format_household_date(household, timezone.now())
    return render(request, "home.html", context)
