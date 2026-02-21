import re

import pytest
from django.core import mail
from django.urls import reverse

from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_password_reset_email_has_a_working_link(client, user):
    response = client.post(reverse("accounts:password_reset"), {"email": "owner@example.com"})

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    link = re.search(r"http://testserver(/accounts/password-reset/\S+/)", mail.outbox[0].body)
    assert link

    # The first visit swaps the token for a session and redirects to a set-password URL.
    response = client.get(link.group(1), follow=True)
    form_url = response.redirect_chain[-1][0]
    response = client.post(
        form_url,
        {"new_password1": "brand-new-password-42", "new_password2": "brand-new-password-42"},
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("brand-new-password-42")


def test_password_reset_for_an_unknown_email_sends_nothing(client, db):
    response = client.post(reverse("accounts:password_reset"), {"email": "nobody@example.com"})

    assert response.status_code == 302
    assert mail.outbox == []


def test_change_password(owner_client, user):
    response = owner_client.post(
        reverse("accounts:password_change"),
        {
            "old_password": PASSWORD,
            "new_password1": "another-good-password-7",
            "new_password2": "another-good-password-7",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("another-good-password-7")


def test_change_password_needs_the_old_one(owner_client, user):
    response = owner_client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "wrong",
            "new_password1": "another-good-password-7",
            "new_password2": "another-good-password-7",
        },
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
