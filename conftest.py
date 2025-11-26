import pytest

from accounts.models import User
from businesses.models import Business

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
