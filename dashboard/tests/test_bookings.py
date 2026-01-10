import pytest
from django.urls import reverse

from appointments.models import Booking
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def test_bookings_list_filters(owner_client, service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10), customer_name="Ana Lima")
    make_booking(
        service, staff, at(monday, 12), customer_name="Bo Chen", status=Booking.Status.CANCELLED
    )

    response = owner_client.get(reverse("dashboard:bookings"), {"status": "cancelled"})

    assert [b.customer_name for b in response.context["bookings"]] == ["Bo Chen"]


def test_bookings_search_by_reference(owner_client, service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10))
    make_booking(service, staff, at(next_weekday(0), 12), customer_name="Someone Else")

    response = owner_client.get(reverse("dashboard:bookings"), {"q": booking.reference.lower()})

    assert list(response.context["bookings"]) == [booking]


def test_bookings_list_is_paginated(owner_client, service, staff):
    monday = next_weekday(0)
    for hour in range(9, 17):
        for minute in (0, 15, 30, 45):
            make_booking(service, staff, at(monday, hour, minute))

    response = owner_client.get(reverse("dashboard:bookings"))

    assert len(response.context["bookings"]) == 25
    assert response.context["page"].paginator.num_pages == 2
