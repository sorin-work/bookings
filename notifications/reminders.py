"""Reminder emails, sent by the send_reminders command (run it from cron)."""

from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from appointments.models import Booking

from . import emails

REMINDER_LEAD = timedelta(hours=24)


def due_reminders(now=None):
    """Confirmed bookings starting in the next 24 hours that haven't had a reminder.

    Bookings made less than a day ahead are skipped: the confirmation email is
    still fresh.
    """
    now = now or timezone.now()
    return Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        reminder_sent_at__isnull=True,
        start__gt=now,
        start__lte=now + REMINDER_LEAD,
        created_at__lte=F("start") - REMINDER_LEAD,
    ).select_related("business", "service", "staff")


def send_due_reminders(now=None):
    now = now or timezone.now()
    sent = 0
    for booking in due_reminders(now):
        # Claim the booking first, so two overlapping runs can't both send it.
        claimed = Booking.objects.filter(pk=booking.pk, reminder_sent_at__isnull=True).update(
            reminder_sent_at=now
        )
        if claimed:
            emails.booking_reminder(booking)
            sent += 1
    return sent
