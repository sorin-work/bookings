import pytest
from django.urls import reverse

from accounts.models import User
from businesses.models import Business

pytestmark = pytest.mark.django_db


def settings_data(business, **overrides):
    data = {
        "name": business.name,
        "slug": business.slug,
        "timezone": business.timezone,
        "email": "",
        "phone": "",
        "address": "",
        "description": "",
        "slot_interval_minutes": 15,
        "min_notice_minutes": 120,
        "max_advance_days": 60,
        "cancellation_notice_hours": 24,
    }
    data.update(overrides)
    return data


def test_settings_page_shows_the_business(owner_client, business):
    response = owner_client.get(reverse("businesses:settings"))

    assert response.status_code == 200
    assert "Fern &amp; Co" in response.content.decode()


def test_save_settings(owner_client, business):
    response = owner_client.post(
        reverse("businesses:settings"),
        settings_data(
            business, name="Fern & Co Hair", timezone="America/New_York", slug="Fern-Hair"
        ),
    )

    assert response.status_code == 302
    business.refresh_from_db()
    assert business.name == "Fern & Co Hair"
    assert business.timezone == "America/New_York"
    assert business.slug == "fern-hair"


def test_unknown_time_zone_is_rejected(owner_client, business):
    response = owner_client.post(
        reverse("businesses:settings"), settings_data(business, timezone="Mars/Olympus_Mons")
    )

    assert response.status_code == 200
    business.refresh_from_db()
    assert business.timezone == "Europe/London"


def test_slug_must_be_unique(owner_client, business):
    other = User.objects.create_user(email="other@example.com", password="x")
    Business.objects.create(owner=other, name="Other", slug="taken")

    response = owner_client.post(
        reverse("businesses:settings"), settings_data(business, slug="taken")
    )

    assert response.status_code == 200
    business.refresh_from_db()
    assert business.slug == "fern-and-co"


def test_notification_email_falls_back_to_the_owner(business):
    assert business.notification_email == "owner@example.com"
    business.email = "desk@example.com"
    assert business.notification_email == "desk@example.com"


def test_account_without_a_business_is_sent_to_setup(client, user):
    client.force_login(user)

    response = client.get(reverse("dashboard:home"))

    assert response.status_code == 302
    assert response["Location"] == reverse("businesses:setup")


def test_setup_creates_a_business(client, user):
    client.force_login(user)

    response = client.post(
        reverse("businesses:setup"),
        {"name": "Corner Physio", "slug": "", "timezone": "Europe/Dublin", "email": ""},
    )

    assert response.status_code == 302
    business = Business.objects.get(owner=user)
    assert business.slug == "corner-physio"
    assert business.timezone == "Europe/Dublin"
