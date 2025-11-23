import pytest

from accounts.models import User

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@example.com", password=PASSWORD)
