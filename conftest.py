from datetime import time
from decimal import Decimal

import pytest

from accounts.models import User
from businesses.models import Business, Service, StaffMember, WorkingHours

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _plain_static_files(settings):
    """The manifest storage needs collectstatic; tests don't run it."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@example.com", password=PASSWORD)


@pytest.fixture
def business(user):
    return Business.objects.create(
        owner=user, name="Fern & Co", slug="fern-and-co", timezone="Europe/London"
    )


@pytest.fixture
def owner_client(client, business):
    client.force_login(business.owner)
    return client


@pytest.fixture
def service(business):
    return Service.objects.create(
        business=business,
        name="Haircut",
        duration_minutes=45,
        price=Decimal("35.00"),
        buffer_after_minutes=15,
    )


@pytest.fixture
def staff(business, service):
    member = StaffMember.objects.create(business=business, name="Robin", email="robin@example.com")
    member.services.add(service)
    for weekday in range(5):
        WorkingHours.objects.create(
            staff=member, weekday=weekday, start_time=time(9), end_time=time(17)
        )
    return member
