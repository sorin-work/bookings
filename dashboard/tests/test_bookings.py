import csv
import io
from datetime import time

import pytest
from django.core import mail
from django.urls import reverse

from appointments.models import Booking
from businesses.models import StaffMember
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def manual_data(service, staff, day, hour, **overrides):
    data = {
        "service": service.pk,
        "staff": staff.pk,
        "date": day.isoformat(),
        "time": time(hour).strftime("%H:%M"),
        "customer_name": "Walk In",
        "customer_email": "walk.in@example.com",
        "customer_phone": "07700900999",
    }
    data.update(overrides)
    return data


def test_add_a_booking_from_the_dashboard(
    owner_client, service, staff, django_capture_on_commit_callbacks
):
    monday = next_weekday(0)

    with django_capture_on_commit_callbacks(execute=True):
        response = owner_client.post(
            reverse("dashboard:booking_new"), manual_data(service, staff, monday, 11)
        )

    assert response.status_code == 302
    booking = Booking.objects.get()
    assert booking.start == at(monday, 11)
    assert booking.source == Booking.Source.DASHBOARD
    # The customer is emailed, the business isn't told about its own booking.
    assert [m.to for m in mail.outbox] == [["walk.in@example.com"]]


def test_dashboard_booking_must_be_free(owner_client, service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 11))

    response = owner_client.post(
        reverse("dashboard:booking_new"), manual_data(service, staff, monday, 11)
    )

    assert response.status_code == 200
    assert Booking.objects.count() == 1


def test_staff_must_offer_the_service(owner_client, business, service, staff):
    other = StaffMember.objects.create(business=business, name="Kit")

    response = owner_client.post(
        reverse("dashboard:booking_new"), manual_data(service, other, next_weekday(0), 11)
    )

    assert response.status_code == 200
    assert "offer Haircut" in response.content.decode()


def test_override_books_outside_working_hours(owner_client, service, staff):
    saturday = next_weekday(5)

    response = owner_client.post(
        reverse("dashboard:booking_new"),
        manual_data(service, staff, saturday, 10, override="on"),
    )

    assert response.status_code == 302
    assert Booking.objects.get().start == at(saturday, 10)


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


def test_csv_export(owner_client, service, staff):
    make_booking(service, staff, at(next_weekday(0), 10), customer_name='=HYPERLINK("x")')

    response = owner_client.get(reverse("dashboard:bookings_csv"))

    rows = list(csv.reader(io.StringIO(response.content.decode())))
    assert rows[0][:3] == ["Reference", "Date", "Start"]
    assert rows[1][2] == "10:00"
    assert rows[1][6] == "'" + '=HYPERLINK("x")'


def test_cancelling_twice_sends_one_email(
    owner_client, service, staff, django_capture_on_commit_callbacks
):
    booking = make_booking(service, staff, at(next_weekday(0), 10))
    url = reverse("dashboard:booking_cancel", args=[booking.pk])

    with django_capture_on_commit_callbacks(execute=True):
        owner_client.post(url)
        owner_client.post(url)

    assert len(mail.outbox) == 1


def test_customer_list_groups_bookings_by_email(owner_client, service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10))
    make_booking(service, staff, at(monday, 12))
    make_booking(
        service, staff, at(monday, 14), customer_name="Bo Chen", customer_email="bo@example.com"
    )

    response = owner_client.get(reverse("dashboard:customers"))

    rows = list(response.context["page"].object_list)
    assert [(row["name"], row["bookings"]) for row in rows] == [("Ana Lima", 2), ("Bo Chen", 1)]


def test_customer_page(owner_client, service, staff):
    make_booking(service, staff, at(next_weekday(0), 10))

    response = owner_client.get(reverse("dashboard:customer"), {"email": "ana@example.com"})

    assert response.status_code == 200
    assert len(response.context["upcoming"]) == 1


def test_unknown_customer_is_a_404(owner_client, business):
    response = owner_client.get(reverse("dashboard:customer"), {"email": "who@example.com"})

    assert response.status_code == 404


def test_private_note(owner_client, service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    owner_client.post(
        reverse("dashboard:booking_note", args=[booking.pk]), {"internal_note": "Prefers Kit"}
    )

    booking.refresh_from_db()
    assert booking.internal_note == "Prefers Kit"
