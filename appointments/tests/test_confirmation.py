from datetime import timedelta
from io import StringIO
from urllib.parse import urlencode

import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from appointments.models import Booking
from appointments.services import Customer, create_booking
from appointments.tokens import make_token
from scheduling import availability
from testutils import at, next_weekday

pytestmark = pytest.mark.django_db


@pytest.fixture
def needs_confirmation(business):
    business.require_confirmation = True
    business.save()
    return business


def book(client, business, service, staff, start):
    url = reverse("appointments:book", args=[business.slug, service.pk])
    return client.post(
        url + "?" + urlencode({"start": start.isoformat(), "staff": staff.pk}),
        {"name": "Ana Lima", "email": "ana@example.com", "phone": "07700900123"},
    )


def test_booking_waits_for_confirmation(client, needs_confirmation, service, staff):
    start = at(next_weekday(0), 10)

    book(client, needs_confirmation, service, staff, start)

    booking = Booking.objects.get()
    assert booking.status == Booking.Status.PENDING
    assert booking.hold_expires_at > timezone.now()
    assert not availability.is_available(service, staff, start)


def test_confirm_from_the_link(
    client, needs_confirmation, service, staff, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        book(client, needs_confirmation, service, staff, at(next_weekday(0), 10))
    booking = Booking.objects.get()
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(reverse("appointments:manage_confirm", args=[make_token(booking)]))

    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.hold_expires_at is None
    assert any("confirmed" in message.subject.lower() for message in mail.outbox)


def test_late_confirmation_still_works_when_the_time_is_free(
    client, needs_confirmation, service, staff
):
    book(client, needs_confirmation, service, staff, at(next_weekday(0), 10))
    booking = Booking.objects.get()
    booking.hold_expires_at = timezone.now() - timedelta(minutes=5)
    booking.save()

    client.post(reverse("appointments:manage_confirm", args=[make_token(booking)]))

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED


def test_expire_command(needs_confirmation, service, staff, client):
    book(client, needs_confirmation, service, staff, at(next_weekday(0), 10))
    Booking.objects.update(hold_expires_at=timezone.now() - timedelta(minutes=1))
    out = StringIO()

    call_command("expire_bookings", stdout=out)

    assert Booking.objects.get().status == Booking.Status.EXPIRED
    assert "Expired 1 unconfirmed booking." in out.getvalue()


def test_bookings_from_the_dashboard_skip_confirmation(needs_confirmation, service, staff):
    booking = create_booking(
        service,
        at(next_weekday(0), 10),
        Customer("Ana", "ana@example.com", "07700900123"),
        staff,
        source=Booking.Source.DASHBOARD,
    )

    assert booking.status == Booking.Status.CONFIRMED
