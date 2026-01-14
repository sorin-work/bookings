import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_landing_page_for_visitors(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert reverse("accounts:signup") in response.content.decode()


def test_signed_in_users_go_to_the_dashboard(owner_client):
    response = owner_client.get(reverse("core:home"))

    assert response.status_code == 302
    assert response["Location"] == reverse("dashboard:home")
