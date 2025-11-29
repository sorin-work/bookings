from decimal import Decimal

import pytest

from accounts.models import User
from businesses.models import Business, Service

PASSWORD = "correct-horse-battery-staple"


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
