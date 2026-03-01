import pytest
from django.test import Client
from django.urls import reverse

from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def test_htmx_request_without_a_session_redirects_the_whole_page(client):
    response = client.get(reverse("dashboard:calendar"), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert response["HX-Redirect"].startswith(reverse("accounts:login"))


def test_normal_requests_still_get_a_redirect(client):
    response = client.get(reverse("dashboard:calendar"))

    assert response.status_code == 302


def test_htmx_requests_send_the_csrf_token(business, service, staff):
    client = Client(enforce_csrf_checks=True)
    client.force_login(business.owner)
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    page = client.get(reverse("dashboard:calendar"))
    token = page.cookies["csrftoken"].value
    assert 'hx-headers=\'{"X-CSRFToken": "' in page.content.decode()

    response = client.post(
        reverse("dashboard:booking_cancel", args=[booking.pk]),
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 200
