"""Helpers shared by the tests."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from appointments.models import Booking

LONDON = ZoneInfo("Europe/London")


def next_weekday(weekday, weeks_ahead=1):
    """A date `weeks_ahead` weeks from now that falls on `weekday` (0 = Monday)."""
    today = timezone.localdate()
    return today + timedelta(days=(weekday - today.weekday()) % 7 + 7 * weeks_ahead)


def at(day, hour, minute=0, tz=LONDON):
    """An aware datetime on `day` at hour:minute in `tz`."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)


def make_booking(service, staff, start, **fields):
    """A booking straight in the database, without the checks in services."""
    values = {
        "business": service.business,
        "service": service,
        "staff": staff,
        "start": start,
        "end": start + timedelta(minutes=service.duration_minutes),
        "buffer_before_minutes": service.buffer_before_minutes,
        "buffer_after_minutes": service.buffer_after_minutes,
        "price": service.price,
        "customer_name": "Ana Lima",
        "customer_email": "ana@example.com",
        "customer_phone": "07700900123",
    }
    values.update(fields)
    return Booking.objects.create(**values)
