import pytest
from django.urls import reverse

from accounts.models import User
from businesses.models import Business
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def signup_data(**overrides):
    data = {
        "email": "new@example.com",
        "password1": "a-long-and-unusual-password",
        "password2": "a-long-and-unusual-password",
        "business_name": "Studio One",
        "timezone": "Europe/Berlin",
    }
    data.update(overrides)
    return data


def test_sign_up_creates_an_account_and_logs_in(client):
    response = client.post(reverse("accounts:signup"), signup_data())

    assert response.status_code == 302
    user = User.objects.get(email="new@example.com")
    assert client.session["_auth_user_id"] == str(user.pk)


def test_sign_up_creates_the_business(client):
    client.post(reverse("accounts:signup"), signup_data())

    business = Business.objects.get(owner__email="new@example.com")
    assert business.name == "Studio One"
    assert business.slug == "studio-one"
    assert business.timezone == "Europe/Berlin"


def test_sign_up_with_a_business_name_that_is_taken_gets_its_own_slug(client):
    client.post(reverse("accounts:signup"), signup_data())
    client.logout()

    response = client.post(reverse("accounts:signup"), signup_data(email="other@example.com"))

    assert response.status_code == 302
    assert Business.objects.get(owner__email="other@example.com").slug == "studio-one-2"


def test_sign_up_rejects_an_email_that_is_taken(client, user):
    response = client.post(reverse("accounts:signup"), signup_data(email="OWNER@example.com"))

    assert response.status_code == 200
    assert "already an account" in response.content.decode()


def test_sign_up_rejects_mismatched_passwords(client):
    response = client.post(reverse("accounts:signup"), signup_data(password2="something-else"))

    assert response.status_code == 200
    assert not User.objects.filter(email="new@example.com").exists()


def test_log_in_with_any_case_email(client, user):
    response = client.post(
        reverse("accounts:login"), {"username": "Owner@Example.com", "password": PASSWORD}
    )

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


def test_log_in_with_a_wrong_password(client, user):
    response = client.post(
        reverse("accounts:login"), {"username": "owner@example.com", "password": "nope"}
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_log_out(client, user):
    client.force_login(user)

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


def test_signed_in_pages_need_a_login(client):
    response = client.get(reverse("dashboard:home"))

    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:login"))
