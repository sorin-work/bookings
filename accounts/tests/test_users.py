import pytest
from django.db import IntegrityError

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_create_user_normalises_the_email():
    user = User.objects.create_user(email="Someone@Example.COM", password="a-long-password")

    assert user.email == "someone@example.com"
    assert user.check_password("a-long-password")
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_requires_an_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="a-long-password")


def test_create_superuser_sets_the_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="a-long-password")

    assert admin.is_staff
    assert admin.is_superuser


def test_emails_are_unique():
    User.objects.create_user(email="dup@example.com", password="x")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="y")
