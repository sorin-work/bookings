from datetime import timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from appointments.models import Booking
from notifications.reminders import due_reminders, send_due_reminders
from testutils import make_booking

pytestmark = pytest.mark.django_db


def booked_ahead(service, staff, hours_from_now, **fields):
    """A booking made a week ago, starting `hours_from_now` from now."""
    now = timezone.now()
    booking = make_booking(service, staff, now + timedelta(hours=hours_from_now), **fields)
    Booking.objects.filter(pk=booking.pk).update(created_at=now - timedelta(days=7))
    booking.refresh_from_db()
    return booking


def test_reminder_for_tomorrow(service, staff):
    booking = booked_ahead(service, staff, 20)

    sent = send_due_reminders()

    assert sent == 1
    assert mail.outbox[0].to == ["ana@example.com"]
    assert mail.outbox[0].subject.startswith("Reminder: Haircut")
    booking.refresh_from_db()
    assert booking.reminder_sent_at is not None


def test_reminders_are_only_sent_once(service, staff):
    booked_ahead(service, staff, 20)

    send_due_reminders()
    send_due_reminders()

    assert len(mail.outbox) == 1


def test_no_reminder_too_early_or_for_cancelled_bookings(service, staff):
    booked_ahead(service, staff, 30)
    booked_ahead(service, staff, 10, status=Booking.Status.CANCELLED)

    assert list(due_reminders()) == []


def test_no_reminder_for_bookings_made_less_than_a_day_ahead(service, staff):
    make_booking(service, staff, timezone.now() + timedelta(hours=6))

    assert list(due_reminders()) == []


def test_command(service, staff):
    booked_ahead(service, staff, 3)
    out = StringIO()

    call_command("send_reminders", stdout=out)

    assert "Sent 1 reminder." in out.getvalue()
