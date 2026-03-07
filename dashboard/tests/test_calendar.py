from datetime import date, timedelta

import pytest
from django.urls import reverse

from accounts.models import User
from appointments.models import Booking
from businesses.models import Business, TimeOff
from dashboard import calendar
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def test_day_grid_places_bookings_in_their_staff_column(business, service, staff):
    monday = next_weekday(0)
    booking = make_booking(service, staff, at(monday, 10))

    grid = calendar.day_grid(business, monday, [staff])

    assert grid.start_hour == 9
    assert grid.end_hour == 17
    [column] = grid.columns
    [event] = column.events
    assert event.booking == booking
    # 10:00 is one hour into an eight hour day; 45 minutes long.
    assert event.top == pytest.approx(12.5)
    assert event.height == pytest.approx(9.375)


def test_day_grid_defaults_to_eight_till_six_without_hours(business, service, staff):
    staff.working_hours.all().delete()

    grid = calendar.day_grid(business, next_weekday(0), [staff])

    assert (grid.start_hour, grid.end_hour) == (8, 18)


def test_week_grid_has_monday_to_sunday(business, service, staff):
    wednesday = next_weekday(2)
    make_booking(service, staff, at(wednesday, 11))

    grid = calendar.week_grid(business, wednesday, [staff])

    days = [column.day for column in grid.columns]
    assert days[0] == wednesday - timedelta(days=2)
    assert days[-1] == wednesday + timedelta(days=4)
    assert len(grid.columns[2].events) == 1


def test_calendar_page(owner_client, service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10), customer_name="Bea Cole")

    response = owner_client.get(reverse("dashboard:calendar"), {"date": monday.isoformat()})

    assert response.status_code == 200
    assert "Bea Cole" in response.content.decode()


def test_calendar_week_view(owner_client, service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday + timedelta(days=3), 10), customer_name="Bea Cole")

    response = owner_client.get(
        reverse("dashboard:calendar"), {"date": monday.isoformat(), "view": "week"}
    )

    assert response.status_code == 200
    assert "Bea Cole" in response.content.decode()


def test_htmx_navigation_gets_just_the_calendar(owner_client, staff):
    response = owner_client.get(reverse("dashboard:calendar"), HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert "<html" not in response.content.decode()


def test_booking_panel(owner_client, service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10), customer_name="Bea Cole")

    response = owner_client.get(
        reverse("dashboard:booking", args=[booking.pk]), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 200
    assert "Bea Cole" in response.content.decode()
    assert "panel" in response.content.decode()


def test_mark_a_past_booking_completed(owner_client, service, staff):
    booking = make_booking(service, staff, at(date.today() - timedelta(days=1), 10))

    owner_client.post(
        reverse("dashboard:booking_outcome", args=[booking.pk]), {"status": "completed"}
    )

    booking.refresh_from_db()
    assert booking.status == Booking.Status.COMPLETED


def test_future_bookings_cannot_be_marked_as_no_show(owner_client, service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    owner_client.post(
        reverse("dashboard:booking_outcome", args=[booking.pk]), {"status": "no_show"}
    )

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED


def test_cancel_from_the_dashboard(owner_client, service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    response = owner_client.post(
        reverse("dashboard:booking_cancel", args=[booking.pk]), HTTP_HX_REQUEST="true"
    )

    assert response["HX-Trigger"] == "bookingChanged"
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.cancelled_by == Booking.CancelledBy.BUSINESS


def test_other_businesses_bookings_are_hidden(client, service, staff):
    other = User.objects.create_user(email="other@example.com", password="x")
    Business.objects.create(owner=other, name="Other", slug="other")
    booking = make_booking(service, staff, at(next_weekday(0), 10))
    client.force_login(other)

    assert client.get(reverse("dashboard:booking", args=[booking.pk])).status_code == 404


def test_mistyped_date_shows_today(owner_client, business, staff):
    response = owner_client.get(reverse("dashboard:calendar"), {"date": "2026-13-45"})

    assert response.status_code == 200
    assert response.context["day"] == business.today()


@pytest.mark.parametrize("day", [date(2026, 1, 5), date(2026, 1, 8), date(2026, 1, 11)])
def test_week_starts_on_monday_for_every_day_of_the_week(day):
    assert calendar.week_start(day) == date(2026, 1, 5)


def test_time_off_shows_in_the_grid(business, staff):
    monday = next_weekday(0)
    TimeOff.objects.create(staff=staff, start=at(monday, 13), end=at(monday, 15), reason="Dentist")

    grid = calendar.day_grid(business, monday, [staff])

    [block] = grid.columns[0].blocks
    assert block.label == "Dentist"
    assert block.top == pytest.approx(50)
