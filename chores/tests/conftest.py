"""Fixtures every test module in this package inherits.

There is one, and it exists because of a trap that costs an afternoon the first
time it is hit: see `unhashed_static` below. It lives here rather than in a
single test module so that the next file to render a template does not
rediscover it.
"""

import pytest


@pytest.fixture(autouse=True)
def unhashed_static(settings):
    """Serve static files without a staticfiles manifest.

    The project stores static files with WhiteNoise's manifest backend, which
    skips hashing while `DEBUG` is on -- so `runserver` is fine -- but the test
    runner forces `DEBUG=False`, and then every `{% static %}` tag raises
    `Missing staticfiles manifest entry` until `collectstatic` has been run.
    Every admin template opens with `{% static 'admin/css/base.css' %}` and
    every page of ours opens with `{% static 'css/app.css' %}`, so without this
    the suite would only be asserting that somebody ran a build step.

    `test_collectstatic_hashes_app_css` deliberately puts the real backend back,
    because something still has to prove the manifest itself works.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
