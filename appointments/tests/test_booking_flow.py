from datetime import time
from urllib.parse import urlencode

import pytest
from django.urls import reverse

from appointments.models import Booking
from appointments.services import Customer, SlotUnavailable, create_booking
from businesses.models import Service, StaffMember, WorkingHours
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def customer_data(**overrides):
    data = {"name": "Ana Lima", "email": "ana@example.com", "phone": "07700900123"}
    data.update(overrides)
    return data


def book_url(business, service, start, staff=None):
    query = {"start": start.isoformat()}
    if staff:
        query["staff"] = staff.pk
    return reverse("appointments:book", args=[business.slug, service.pk]) + "?" + urlencode(query)


def test_business_page_lists_bookable_services(client, business, service, staff):
    Service.objects.create(business=business, name="Nobody does this", duration_minutes=30, price=5)

    response = client.get(reverse("appointments:business", args=[business.slug]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Haircut" in content
    assert "Nobody does this" not in content


def test_unknown_business_is_a_404(client, db):
    assert client.get(reverse("appointments:business", args=["nope"])).status_code == 404


def test_service_page_shows_free_times(client, business, service, staff):
    monday = next_weekday(0)

    response = client.get(
        reverse("appointments:service", args=[business.slug, service.pk]),
        {"date": monday.isoformat()},
    )

    assert response.status_code == 200
    assert response.context["day"] == monday
    assert at(monday, 9) in response.context["times"]


def test_slots_partial_for_another_day(client, business, service, staff):
    tuesday = next_weekday(1)

    response = client.get(
        reverse("appointments:slots", args=[business.slug, service.pk]),
        {"date": tuesday.isoformat()},
    )

    assert response.status_code == 200
    assert "09:00" in response.content.decode()


def test_book_a_time(client, business, service, staff):
    start = at(next_weekday(0), 10)

    response = client.post(book_url(business, service, start, staff), customer_data())

    booking = Booking.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"{booking.manage_url}?new=1"
    assert booking.start == start
    assert booking.staff == staff
    assert booking.customer_email == "ana@example.com"
    assert booking.price == service.price
    assert booking.buffer_after_minutes == 15
    assert booking.status == Booking.Status.CONFIRMED


def test_anyone_available_goes_to_the_least_busy_staff_member(client, business, service, staff):
    other = StaffMember.objects.create(business=business, name="Kit")
    other.services.add(service)
    WorkingHours.objects.create(staff=other, weekday=0, start_time=time(9), end_time=time(17))
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 9))

    client.post(book_url(business, service, at(monday, 14)), customer_data())

    assert Booking.objects.get(start=at(monday, 14)).staff == other


def test_taken_time_sends_the_customer_back(client, business, service, staff):
    start = at(next_weekday(0), 10)
    make_booking(service, staff, start)

    response = client.get(book_url(business, service, start, staff))

    assert response.status_code == 302
    assert response["Location"].startswith(
        reverse("appointments:service", args=[business.slug, service.pk])
    )


def test_missing_details_are_rejected(client, business, service, staff):
    start = at(next_weekday(0), 10)

    response = client.post(book_url(business, service, start, staff), customer_data(email="nope"))

    assert response.status_code == 200
    assert not Booking.objects.exists()


def test_start_must_be_a_time(client, business, service, staff):
    url = reverse("appointments:book", args=[business.slug, service.pk]) + "?start=tomorrow"

    assert client.get(url).status_code == 404


@pytest.mark.parametrize("value", ["", "31-12-2030", "soon"])
def test_slots_without_a_proper_day_are_a_404(client, business, service, staff, value):
    url = reverse("appointments:slots", args=[business.slug, service.pk])

    assert client.get(url, {"date": value}).status_code == 404


def test_create_booking_checks_the_time_again(service, staff):
    start = at(next_weekday(0), 10)
    make_booking(service, staff, start)

    with pytest.raises(SlotUnavailable):
        create_booking(service, start, Customer("Bo", "bo@example.com", "07700900456"), staff)


def test_honeypot_stops_bots(client, business, service, staff):
    start = at(next_weekday(0), 10)

    response = client.post(
        book_url(business, service, start, staff), customer_data(website="http://spam.example")
    )

    assert response.status_code == 200
    assert not Booking.objects.exists()
