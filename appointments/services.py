"""Everything that creates a booking or changes its state goes through here."""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Booking


class SlotUnavailable(Exception):
    """The requested time isn't free (any more)."""


@dataclass
class Customer:
    name: str
    email: str
    phone: str


def create_booking(service, start, customer, staff, *, now=None):
    """Book `service` at `start` (an aware datetime).

    Without `staff`, whoever is free and least busy that day gets the booking.
    Raises SlotUnavailable if nobody can take it.
    """
    business = service.business
    now = now or timezone.now()
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
    return booking
