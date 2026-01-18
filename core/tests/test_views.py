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


def test_admin_pages_load(admin_client, service, staff):
    for name in [
        "accounts_user",
        "businesses_business",
        "businesses_staffmember",
        "businesses_timeoff",
        "appointments_booking",
    ]:
        response = admin_client.get(reverse(f"admin:{name}_changelist"))
        assert response.status_code == 200, name
