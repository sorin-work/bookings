"""Everything that creates a booking or changes its state goes through here."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from businesses.models import StaffMember
from notifications import emails
from scheduling import availability

from .models import Booking


class SlotUnavailable(Exception):
    """The requested time isn't free (any more)."""


@dataclass
class Customer:
    name: str
    email: str
    phone: str


def _day_bounds(business, start):
    day = start.astimezone(business.tz).date()
    first = datetime.combine(day, time(0), tzinfo=business.tz)
    return first, first + timedelta(days=1)


def _least_busy_first(business, members, start):
    """Spread "anyone available" bookings: the member with the fewest bookings that day first."""
    day_start, day_end = _day_bounds(business, start)
    counts = dict(
        StaffMember.objects.filter(pk__in=[m.pk for m in members])
        .annotate(
            n=Count(
                "bookings",
                filter=Q(bookings__start__gte=day_start, bookings__start__lt=day_end)
                & ~Q(bookings__status__in=Booking.CLOSED_STATUSES),
            )
        )
        .values_list("pk", "n")
    )
    return sorted(members, key=lambda m: (counts.get(m.pk, 0), m.name, m.pk))


def free_staff(service, start, staff=None, now=None):
    """Staff who can take `service` at `start`, least busy first."""
    candidates = [staff] if staff else list(availability.bookable_staff(service))
    free = [m for m in candidates if availability.is_available(service, m, start, now=now)]
    return _least_busy_first(service.business, free, start)


def create_booking(service, start, customer, staff=None, *, now=None):
    """Book `service` at `start` (an aware datetime).

    Without `staff`, whoever is free and least busy that day gets the booking.
    Raises SlotUnavailable if nobody can take it.
    """
    business = service.business
    now = now or timezone.now()
    if staff is None:
        free = free_staff(service, start, now=now)
        if not free:
            raise SlotUnavailable
        staff = free[0]
    with transaction.atomic():
        booking = Booking.objects.create(
            business=business,
            service=service,
            staff=staff,
            start=start,
            end=start + timedelta(minutes=service.duration_minutes),
            buffer_before_minutes=service.buffer_before_minutes,
            buffer_after_minutes=service.buffer_after_minutes,
            price=service.price,
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
        )
        emails.booking_created(booking)
    return booking


def cancel_booking(booking, by, *, now=None):
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = now or timezone.now()
    booking.cancelled_by = by
    booking.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
    return booking


def reschedule_booking(booking, start, *, now=None):
    """Move a booking to a new start time with the same staff member."""
    now = now or timezone.now()
    with transaction.atomic():
        if not availability.is_available(booking.service, booking.staff, start, now=now):
            raise SlotUnavailable
        duration = booking.end - booking.start
        booking.start = start
        booking.end = start + duration
        booking.save(update_fields=["start", "end", "updated_at"])
    return booking
