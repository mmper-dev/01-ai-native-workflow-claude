import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_page_responds(client):
    response = client.get(reverse("chores:home"))
    assert response.status_code == 200
