import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_responds(client):
    """`/` is wired up and answers.

    It used to answer 200 to anybody. Since issue #8 it requires login, so the
    smoke test asserts the redirect an anonymous visitor gets -- Django's
    default LOGIN_URL is where allauth is mounted.
    """
    response = client.get(reverse("chores:home"))
    assert response.status_code == 302
    assert response.headers["Location"] == "/accounts/login/?next=/"
