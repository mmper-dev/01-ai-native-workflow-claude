"""Tests for issue #8 -- base templates and authentication pages.

One test per acceptance criterion on the issue, in the order they are listed
there, as the other test modules do. Everything that can go through the real
URLs does: the criterion is that a person can sign up, log in, log out and log
back in, and `force_login` would prove none of that.
"""

import datetime
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import time_machine
from django.core.management import call_command
from django.test import Client

from chores.models import Household, Membership, User
from chores.views import format_household_date

BASE_DIR = Path(__file__).resolve().parents[2]
APP_CSS = BASE_DIR / "static" / "css" / "app.css"
TEMPLATES_DIR = BASE_DIR / "templates"

HOME_URL = "/"
LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"
LOGOUT_URL = "/accounts/logout/"

PASSWORD = "correct-horse-battery"

NO_HOUSEHOLD_TEXT = (
    "You're not in a household yet. A household admin has to add you before you'll see any chores."
)
NOTHING_DUE_TEXT = "Nothing is due right now."

# Every token name in the design system's "Tokens" block, in its order.
DESIGN_SYSTEM_TOKENS = [
    "--color-bg-page",
    "--color-surface-card",
    "--color-surface-muted",
    "--color-border",
    "--color-border-strong",
    "--color-text-primary",
    "--color-text-secondary",
    "--color-text-muted",
    "--color-text-on-dark",
    "--color-state-overdue-surface",
    "--color-state-overdue-border",
    "--color-state-overdue-text",
    "--color-state-done-surface",
    "--color-state-done-border",
    "--color-state-done-text",
    "--color-state-unclaimed-surface",
    "--color-state-unclaimed-border",
    "--color-state-unclaimed-text",
    "--color-action-primary",
    "--color-action-primary-hover",
    "--color-action-danger",
    "--color-action-danger-hover",
    "--color-action-disabled-bg",
    "--color-focus-ring",
    "--font-sans",
    "--text-xs",
    "--leading-xs",
    "--text-sm",
    "--leading-sm",
    "--text-base",
    "--leading-base",
    "--text-lg",
    "--leading-lg",
    "--text-xl",
    "--leading-xl",
    "--weight-regular",
    "--weight-semibold",
    "--space-1",
    "--space-2",
    "--space-3",
    "--space-4",
    "--space-5",
    "--space-6",
    "--space-7",
    "--radius-sm",
    "--radius-md",
    "--radius-pill",
    "--border-width",
    "--border-width-thick",
    "--focus-ring-width",
    "--focus-ring-offset",
    "--touch-min",
    "--layout-max-width",
]

# Spot checks that the values were copied, not approximated.
DESIGN_SYSTEM_VALUES = {
    "--color-bg-page": "#f4f4f5",
    "--color-border-strong": "#71717a",
    "--color-state-overdue-border": "#dc2626",
    "--color-action-primary": "#1d4ed8",
    "--text-base": "1rem",
    "--space-4": "1rem",
    "--radius-md": "8px",
    "--border-width-thick": "2px",
    "--focus-ring-width": "3px",
    "--touch-min": "2.75rem",
    "--layout-max-width": "34rem",
}


# Fixtures and helpers


@pytest.fixture
def member(db):
    return User.objects.create_user(username="ana", email="ana@example.com", password=PASSWORD)


@pytest.fixture
def household(db):
    return Household.objects.create(name="Rose Cottage", timezone="UTC")


def page(client, url, **kwargs):
    """GET a URL and hand back its rendered HTML."""
    return client.get(url, **kwargs).content.decode()


def global_bar(html: str) -> str:
    match = re.search(r"<header class=\"global-bar\">.*?</header>", html, re.DOTALL)
    assert match, "the global bar is missing from the page"
    return match.group(0)


def sign_up(client, email, password=PASSWORD, follow=False, **extra):
    return client.post(
        SIGNUP_URL,
        {"email": email, "password1": password, "password2": password, **extra},
        follow=follow,
    )


def log_in(client, email, password=PASSWORD, follow=False, **extra):
    return client.post(LOGIN_URL, {"login": email, "password": password, **extra}, follow=follow)


def is_signed_in(client) -> bool:
    """Ask the server, not the cookie jar -- a stale session cookie lies."""
    return client.get(HOME_URL).status_code == 200


@pytest.fixture
def app_css() -> str:
    return APP_CSS.read_text(encoding="utf-8")


# The shell -- templates/base.html


@pytest.mark.django_db
@pytest.mark.parametrize("url", [LOGIN_URL, SIGNUP_URL])
def test_base_is_one_complete_html_document(client, url):
    html = page(client, url)
    assert html.lower().count("<!doctype html>") == 1
    assert '<html lang="en">' in html
    assert '<meta charset="utf-8">' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "<title>" in html


@pytest.mark.django_db
def test_base_has_a_title_block_and_a_content_block(client):
    """Both blocks are real: the pages that extend it fill them in."""
    assert "<title>Log in</title>" in page(client, LOGIN_URL)
    assert "<title>Sign up</title>" in page(client, SIGNUP_URL)


@pytest.mark.django_db
@pytest.mark.parametrize("url", [LOGIN_URL, SIGNUP_URL])
def test_exactly_one_stylesheet_and_no_inline_style(client, url):
    html = page(client, url)
    assert html.count('rel="stylesheet"') == 1
    assert "css/app.css" in html
    assert "<style" not in html
    assert "style=" not in html


def test_no_template_carries_a_style_block_or_attribute():
    """The rule is about the templates, not just about one rendered page."""
    for template in TEMPLATES_DIR.rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        assert "<style" not in source, template
        assert "style=" not in source, template


def test_content_column_matches_the_layout_spec(app_css):
    column = re.search(r"\.content-column \{(.*?)\}", app_css, re.DOTALL).group(1)
    assert "width: 100%;" in column
    assert "max-width: var(--layout-max-width);" in column
    assert "margin-inline: auto;" in column
    assert "padding-inline: var(--space-4);" in column
    breakpoint_rule = re.search(
        r"@media \(min-width: 480px\) \{\s*\.content-column \{(.*?)\}", app_css, re.DOTALL
    )
    assert breakpoint_rule, "the 480px padding step is missing"
    assert "padding-inline: var(--space-6);" in breakpoint_rule.group(1)


@pytest.mark.django_db
def test_anonymous_bar_is_the_app_name_and_a_log_in_link(client):
    bar = global_bar(page(client, LOGIN_URL))
    assert '<a class="global-bar__brand" href="/">Chores</a>' in bar
    assert "Log in</a>" in bar
    assert "Log out" not in bar


@pytest.mark.django_db
def test_signed_in_bar_shows_full_name_when_it_is_set(client, member):
    member.first_name = "Ana"
    member.last_name = "Ruiz"
    member.save()
    client.force_login(member)
    bar = global_bar(page(client, HOME_URL))
    assert "Ana Ruiz" in bar
    assert member.email not in bar


@pytest.mark.django_db
def test_signed_in_bar_falls_back_to_the_email_never_the_username(client):
    """`{{ user }}` would print "alex3" here -- allauth generates the username."""
    user = User.objects.create_user(username="alex3", email="alex@example.com", password=PASSWORD)
    client.force_login(user)
    bar = global_bar(page(client, HOME_URL))
    assert "alex@example.com" in bar
    assert "alex3" not in bar


@pytest.mark.django_db
def test_bar_carries_nothing_household_specific(client, member, household):
    Membership.objects.create(user=member, household=household)
    client.force_login(member)
    html = page(client, HOME_URL)
    bar = global_bar(html)
    assert household.name not in bar
    # ... while the screen itself does render it.
    assert household.name in html


@pytest.mark.django_db
def test_log_out_in_the_bar_is_a_post_form(client, member):
    client.force_login(member)
    bar = global_bar(page(client, HOME_URL))
    assert '<form class="global-bar__logout" method="post" action="/accounts/logout/">' in bar
    assert "csrfmiddlewaretoken" in bar
    assert '<button type="submit" class="btn btn--quiet">Log out</button>' in bar


@pytest.mark.django_db
def test_a_message_renders_in_the_content_column_with_its_level_word(client, member):
    """allauth greets a successful login with a message; it has to look right."""
    response = log_in(client, member.email, follow=True)
    html = response.content.decode()
    assert '<div class="notice notice--success">' in html
    assert '<span class="notice__level">Success</span>' in html
    # Below the bar, above the content block.
    assert html.index("global-bar") < html.index("notice--success")
    assert html.index("notice--success") < html.index("card--empty")


@pytest.mark.django_db
def test_a_message_appears_once_and_is_gone_next_request(client, member):
    log_in(client, member.email, follow=True)
    assert "notice--success" not in page(client, HOME_URL)


@pytest.mark.django_db
def test_htmx_is_pinned_with_an_integrity_hash(client):
    html = page(client, LOGIN_URL)
    assert "https://cdnjs.cloudflare.com/ajax/libs/htmx/2.0.10/htmx.min.js" in html
    assert (
        'integrity="sha512-5l65kMjGvrm7EATevCK/SFdMUfIUQfAsQLZY57t7tmsPf5ZtjrzU8w'
        'zSBykpRDhqnMwlKISCrxQTURFULsXdpQ=="' in html
    )
    assert 'crossorigin="anonymous"' in html


@pytest.mark.django_db
def test_alpine_is_not_loaded(client):
    assert "alpine" not in page(client, LOGIN_URL).lower()


@pytest.mark.django_db
def test_one_inline_script_and_it_is_the_htmx_error_listener(client):
    html = page(client, LOGIN_URL)
    # Two script tags: HTMX from the CDN, and this listener.
    assert html.count("<script") == 2
    assert "htmx:responseError" in html
    assert "htmx:sendError" in html
    assert "That didn't save. Try again." in html
    assert "notice notice--error" in html


# The stylesheet -- static/css/app.css


def test_app_css_opens_with_the_token_block(app_css):
    root = re.search(r":root \{(.*?)\n\}", app_css, re.DOTALL)
    assert root, "app.css does not open with a :root block"
    assert app_css.index(":root") < app_css.index(".content-column")
    declared = root.group(1)
    for token in DESIGN_SYSTEM_TOKENS:
        assert f"{token}:" in declared, f"{token} is missing from :root"


def test_token_values_are_the_design_systems_own(app_css):
    for token, value in DESIGN_SYSTEM_VALUES.items():
        assert re.search(rf"{re.escape(token)}:\s*{re.escape(value)}\s*;", app_css), token


def test_every_colour_painted_comes_from_a_token(app_css):
    """No raw hex outside the :root block."""
    body = app_css[app_css.index("/* Document */") :]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", body)


def test_the_shared_focus_ring_is_present_and_never_removed(app_css):
    rule = re.search(r":focus-visible \{(.*?)\}", app_css, re.DOTALL)
    assert rule
    assert "outline: var(--focus-ring-width) solid var(--color-focus-ring);" in rule.group(1)
    assert "outline-offset: var(--focus-ring-offset);" in rule.group(1)
    assert "outline: none" not in app_css
    assert "outline:none" not in app_css


def test_buttons_and_fields_clear_the_touch_minimum(app_css):
    button = re.search(r"\n\.btn \{(.*?)\}", app_css, re.DOTALL).group(1)
    assert "min-height: var(--touch-min);" in button
    assert "min-width: var(--touch-min);" in button
    field = re.search(r"\.field__input \{(.*?)\}", app_css, re.DOTALL).group(1)
    assert "min-height: var(--touch-min);" in field
    # 16px, or mobile Safari zooms on focus and does not zoom back.
    assert "font-size: var(--text-base);" in field


def test_app_css_styles_what_number_8_uses_and_stops_there(app_css):
    for selector in [
        ".content-column",
        ".global-bar",
        ".btn--primary",
        ".btn--quiet",
        ".btn.htmx-request",
        ".field__label",
        ".field__input",
        ".field__help",
        ".field__error",
        ".notice--success",
        ".notice--error",
        ".notice--info",
        ".card",
        ".card--empty",
    ]:
        assert selector in app_css, selector
    # #9's components are not written here in advance.
    for not_yet in [".pill", ".card--done", ".day-strip", ".detail-actions"]:
        assert not_yet not in app_css, not_yet


def test_no_build_step_was_introduced():
    for artefact in ["package.json", "package-lock.json", "node_modules"]:
        assert not (BASE_DIR / artefact).exists(), artefact


# The three allauth pages


@pytest.mark.parametrize("name", ["login", "signup", "logout"])
def test_the_three_allauth_templates_extend_base_directly(name):
    source = (TEMPLATES_DIR / "account" / f"{name}.html").read_text(encoding="utf-8")
    assert source.startswith('{% extends "base.html" %}')
    # Not allauth's layouts, and not its themed element tags.
    assert "base_entrance" not in source
    assert "base_manage" not in source
    assert "allauth/layouts" not in source
    assert "{% element" not in source
    assert "as_p" not in source


def test_only_three_allauth_templates_are_overridden():
    overridden = sorted(p.name for p in (TEMPLATES_DIR / "account").glob("*.html"))
    assert overridden == ["login.html", "logout.html", "signup.html"]
    assert not (TEMPLATES_DIR / "allauth").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "heading"),
    [(LOGIN_URL, "Log in"), (SIGNUP_URL, "Sign up")],
)
def test_headings_are_sentence_case(client, url, heading):
    html = page(client, url)
    assert f'<h1 class="page-heading">{heading}</h1>' in html
    assert "Sign In" not in html
    assert "Sign Out" not in html
    assert html.lower().count("<!doctype html>") == 1


@pytest.mark.django_db
def test_logout_page_heading_is_sentence_case(client, member):
    client.force_login(member)
    html = page(client, LOGOUT_URL)
    assert '<h1 class="page-heading">Log out</h1>' in html
    assert "Sign Out" not in html


@pytest.mark.django_db
def test_fields_use_the_design_systems_form_markup(client):
    html = page(client, LOGIN_URL)
    assert '<label class="field__label" for="id_login">Email</label>' in html
    assert '<input class="field__input"' in html
    assert 'type="email"' in html
    assert '<label class="field__label" for="id_password">Password</label>' in html
    assert '<p class="field__help">' in html


@pytest.mark.django_db
@pytest.mark.parametrize(("url", "action"), [(LOGIN_URL, LOGIN_URL), (SIGNUP_URL, SIGNUP_URL)])
def test_each_form_posts_to_its_own_url_with_csrf_and_the_redirect_field(client, url, action):
    html = page(client, url, data={"next": "/somewhere/"})
    assert f'<form class="form" method="post" action="{action}">' in html
    assert "csrfmiddlewaretoken" in html
    assert 'name="next"' in html
    assert 'value="/somewhere/"' in html


@pytest.mark.django_db
@pytest.mark.parametrize(("url", "label"), [(LOGIN_URL, "Log in"), (SIGNUP_URL, "Sign up")])
def test_submit_buttons_are_the_primary_variant(client, url, label):
    html = page(client, url)
    assert f'<button type="submit" class="btn btn--primary">{label}</button>' in html


@pytest.mark.django_db
def test_signup_shows_exactly_three_fields_and_no_username(client):
    html = page(client, SIGNUP_URL)
    names = re.findall(r'<input class="field__input"[^>]*name="([^"]+)"', html, re.DOTALL)
    assert names == ["email", "password1", "password2"]
    assert 'name="username"' not in html


@pytest.mark.django_db
def test_the_remember_checkbox_is_rendered_not_dropped(client):
    html = page(client, LOGIN_URL)
    assert '<div class="field field--checkbox">' in html
    assert 'name="remember"' in html
    assert 'type="checkbox"' in html
    assert '<label class="field__label" for="id_remember">Remember me</label>' in html


@pytest.mark.django_db
def test_remember_me_is_honoured_when_ticked(client, member):
    """Rendered properly means the server still receives it."""
    response = log_in(client, member.email, remember="on")
    assert response.status_code == 302
    assert is_signed_in(client)


@pytest.mark.django_db
def test_get_logout_renders_the_confirmation_and_does_not_log_out(client, member):
    client.force_login(member)
    response = client.get(LOGOUT_URL)
    assert response.status_code == 200
    assert "Are you sure you want to log out?" in response.content.decode()
    assert is_signed_in(client)


# Behaviour


@pytest.mark.django_db
def test_signing_up_creates_the_account_logs_in_and_lands_on_home(client):
    response = sign_up(client, "new@example.com")
    assert response.status_code == 302
    assert response.headers["Location"] == HOME_URL
    assert User.objects.filter(email="new@example.com").exists()
    bar = global_bar(page(client, HOME_URL))
    assert "new@example.com" in bar
    assert "Log out" in bar


@pytest.mark.django_db
def test_signing_up_with_an_existing_email_redisplays_the_form(client, member):
    response = sign_up(client, member.email)
    assert response.status_code == 200
    html = response.content.decode()
    assert '<div class="notice notice--error" role="alert">' in html
    assert "Something needs fixing." in html
    assert 'aria-invalid="true"' in html
    assert 'aria-describedby="id_email-error"' in html
    assert '<p class="field__error" id="id_email-error">' in html
    assert User.objects.filter(email=member.email).count() == 1


@pytest.mark.django_db
def test_two_emails_sharing_a_local_part_both_sign_up():
    """A duplicate username cannot be produced from the form at all."""
    assert sign_up(Client(), "alex@one.example").status_code == 302
    assert sign_up(Client(), "alex@two.example").status_code == 302
    users = User.objects.filter(email__startswith="alex@").order_by("pk")
    assert users.count() == 2
    assert users[0].username != users[1].username


@pytest.mark.django_db
@pytest.mark.parametrize("password", ["short", "password123", "84726194"])
def test_a_password_the_validators_reject_redisplays_as_a_field_error(client, password):
    response = sign_up(client, "weak@example.com", password=password)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'aria-describedby="id_password1-error"' in html
    assert '<p class="field__error" id="id_password1-error">' in html
    assert not User.objects.filter(email="weak@example.com").exists()


@pytest.mark.django_db
def test_logging_in_with_the_wrong_password_keeps_the_email_and_empties_the_password(
    client, member
):
    response = log_in(client, member.email, password="not-the-password")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Something needs fixing." in html
    assert f'value="{member.email}"' in html
    assert "not-the-password" not in html


@pytest.mark.django_db
def test_logging_out_from_the_bar_ends_on_the_login_page(client, member):
    client.force_login(member)
    response = client.post(LOGOUT_URL, follow=True)
    assert response.redirect_chain == [(HOME_URL, 302), ("/accounts/login/?next=/", 302)]
    assert response.status_code == 200
    bar = global_bar(response.content.decode())
    assert "Log in</a>" in bar
    assert member.email not in bar


@pytest.mark.django_db
@pytest.mark.parametrize("url", [LOGIN_URL, SIGNUP_URL])
def test_an_authenticated_person_is_redirected_away_from_login_and_signup(client, member, url):
    client.force_login(member)
    response = client.get(url)
    assert response.status_code == 302
    assert response.headers["Location"] == HOME_URL


@pytest.mark.django_db
def test_anonymous_home_redirects_to_login_and_comes_back(client, member):
    response = client.get(HOME_URL)
    assert response.status_code == 302
    assert response.headers["Location"] == "/accounts/login/?next=/"
    landed = client.post("/accounts/login/?next=/", {"login": member.email, "password": PASSWORD})
    assert landed.status_code == 302
    assert landed.headers["Location"] == HOME_URL


@pytest.mark.django_db
def test_the_whole_loop_through_the_real_urls(client):
    """Sign up, log out, log back in -- no force_login anywhere."""
    assert sign_up(client, "loop@example.com").status_code == 302
    assert is_signed_in(client)

    assert client.post(LOGOUT_URL).status_code == 302
    assert not is_signed_in(client)

    assert log_in(client, "loop@example.com").status_code == 302
    assert is_signed_in(client)


# The landing page at /


@pytest.mark.django_db
def test_a_fresh_signup_lands_on_the_not_in_a_household_empty_state(client):
    response = sign_up(client, "fresh@example.com", follow=True)
    assert response.status_code == 200
    html = response.content.decode()
    assert '<div class="card card--empty">' in html
    assert NO_HOUSEHOLD_TEXT in html


@pytest.mark.django_db
def test_a_member_sees_the_page_header_and_the_nothing_due_card(client, member, household):
    Membership.objects.create(user=member, household=household)
    client.force_login(member)
    html = page(client, HOME_URL)
    assert '<h1 class="page-header__household">Rose Cottage</h1>' in html
    assert '<p class="page-header__date">' in html
    assert NOTHING_DUE_TEXT in html
    assert NO_HOUSEHOLD_TEXT not in html


@pytest.mark.django_db
@time_machine.travel("2026-09-07T23:30:00Z")
def test_the_date_is_computed_in_the_households_timezone(client, member):
    """23:30 UTC is already the next day in Auckland, and the header says so."""
    auckland = Household.objects.create(name="Flat 4b", timezone="Pacific/Auckland")
    Membership.objects.create(user=member, household=auckland)
    client.force_login(member)
    assert '<p class="page-header__date">Tuesday 8 September</p>' in page(client, HOME_URL)


@pytest.mark.django_db
@time_machine.travel("2026-09-07T23:30:00Z")
def test_the_same_instant_is_still_the_previous_day_on_a_utc_household(client, member, household):
    Membership.objects.create(user=member, household=household)
    client.force_login(member)
    assert '<p class="page-header__date">Monday 7 September</p>' in page(client, HOME_URL)


@pytest.mark.django_db
def test_more_than_one_membership_uses_the_lowest_pk(client, member):
    first = Household.objects.create(name="Rose Cottage", timezone="UTC")
    second = Household.objects.create(name="Flat 4b", timezone="UTC")
    older = Membership.objects.create(user=member, household=first)
    newer = Membership.objects.create(user=member, household=second)
    assert older.pk < newer.pk
    client.force_login(member)
    html = page(client, HOME_URL)
    assert "Rose Cottage" in html
    assert "Flat 4b" not in html


def test_the_date_formatter_takes_the_clock_as_an_argument():
    """No `timezone.now()` inside it, so a test can pin the day."""
    household = Household(name="Rose Cottage", timezone="Europe/Athens")
    instant = datetime.datetime(2026, 9, 7, 21, 30, tzinfo=ZoneInfo("UTC"))
    assert format_household_date(household, instant) == "Tuesday 8 September"
    earlier = datetime.datetime(2026, 9, 7, 6, 0, tzinfo=ZoneInfo("UTC"))
    assert format_household_date(household, earlier) == "Monday 7 September"


def test_the_formatted_date_has_no_leading_zero():
    household = Household(name="Rose Cottage", timezone="UTC")
    instant = datetime.datetime(2026, 9, 7, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert format_household_date(household, instant) == "Monday 7 September"


# Static files


def test_collectstatic_hashes_app_css(settings, tmp_path):
    """The real backend, not the `unhashed_static` fixture the rest of the suite uses.

    With `DEBUG=False` and WhiteNoise's manifest storage, a page carrying
    `{% static 'css/app.css' %}` is a 500 until `collectstatic` has produced a
    manifest entry for it -- so something has to prove it does.
    """
    static_root = tmp_path / "staticfiles"
    settings.STATIC_ROOT = static_root
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    call_command("collectstatic", "--no-input", verbosity=0)

    manifest = json.loads((static_root / "staticfiles.json").read_text(encoding="utf-8"))
    hashed = manifest["paths"]["css/app.css"]
    assert re.fullmatch(r"css/app\.[0-9a-f]+\.css", hashed), hashed
    assert (static_root / hashed).exists()
