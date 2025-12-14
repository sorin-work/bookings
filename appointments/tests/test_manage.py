from datetime import timedelta

import pytest
from django.urls import reverse

from appointments.models import Booking
from appointments.tokens import make_token
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


@pytest.fixture
def booking(service, staff):
    return make_booking(service, staff, at(next_weekday(0), 10))


def test_booking_link_shows_the_booking(client, booking):
    response = client.get(booking.manage_url)

    assert response.status_code == 200
    assert booking.reference in response.content.decode()


def test_tampered_link_is_a_404(client, booking):
    token = make_token(booking)

    response = client.get(reverse("appointments:manage", args=[token[:-2] + "xx"]))

    assert response.status_code == 404


def test_cancel_from_the_link(client, booking):
    response = client.post(reverse("appointments:manage_cancel", args=[make_token(booking)]))

    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.cancelled_by == Booking.CancelledBy.CUSTOMER
    assert booking.cancelled_at is not None


def test_cancel_needs_a_post(client, booking):
    response = client.get(reverse("appointments:manage_cancel", args=[make_token(booking)]))

    assert response.status_code == 405


def test_reschedule_page_offers_times(client, booking):
    response = client.get(
        reverse("appointments:manage_reschedule", args=[make_token(booking)]),
        {"date": next_weekday(1).isoformat()},
    )

    assert response.status_code == 200
    assert response.context["times"]


def test_move_to_another_time(client, booking):
    new_start = at(next_weekday(2), 14)

    response = client.post(
        reverse("appointments:manage_reschedule", args=[make_token(booking)]),
        {"start": new_start.isoformat()},
    )

    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.start == new_start
    assert booking.end == new_start + timedelta(minutes=booking.service.duration_minutes)


def test_cannot_move_to_a_taken_time(client, booking, service, staff):
    taken = at(next_weekday(2), 14)
    make_booking(service, staff, taken, customer_email="other@example.com")

    response = client.post(
        reverse("appointments:manage_reschedule", args=[make_token(booking)]),
        {"start": taken.isoformat()},
    )

    assert response.status_code == 200
    booking.refresh_from_db()
    assert booking.start == at(next_weekday(0), 10)
