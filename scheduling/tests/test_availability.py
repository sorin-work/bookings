from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.utils import timezone

from appointments.models import Booking
from businesses.models import StaffMember, TimeOff, WorkingHours
from scheduling import availability
from testutils import LONDON, at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def local_starts(slots):
    return [slot.start.astimezone(LONDON).strftime("%H:%M") for slot in slots]


def test_free_slots_on_a_working_day(service, staff):
    monday = next_weekday(0)

    slots = availability.available_slots(service, monday)

    assert local_starts(slots)[:3] == ["09:00", "09:15", "09:30"]
    assert all(slot.staff_id == staff.pk for slot in slots)


def test_no_slots_at_the_weekend(service, staff):
    assert availability.available_slots(service, next_weekday(5)) == []


def test_a_booking_blocks_its_time_and_buffer(service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10))  # 10:00-10:45, then 15 minutes buffer

    starts = local_starts(availability.available_slots(service, monday))

    assert "10:00" not in starts
    assert "10:30" not in starts
    assert "11:15" in starts


def test_slots_for_anyone_include_every_staff_member(business, service, staff):
    other = StaffMember.objects.create(business=business, name="Kit")
    other.services.add(service)
    WorkingHours.objects.create(staff=other, weekday=0, start_time=time(12), end_time=time(14))
    monday = next_weekday(0)

    anyone = availability.available_slots(service, monday)
    only_kit = availability.available_slots(service, monday, staff=other)

    assert {slot.staff_id for slot in anyone} == {staff.pk, other.pk}
    assert local_starts(only_kit)[0] == "12:00"
    assert availability.start_times(anyone) == sorted(set(availability.start_times(anyone)))


def test_time_off_blocks_slots(service, staff):
    monday = next_weekday(0)
    TimeOff.objects.create(staff=staff, start=at(monday, 0), end=at(monday, 12, 50))

    starts = local_starts(availability.available_slots(service, monday))

    assert starts[0] == "13:00"


def test_minimum_notice(business, service, staff):
    monday = next_weekday(0)
    now = at(monday, 10, 5)

    starts = local_starts(availability.available_slots(service, monday, now=now))

    assert starts[0] == "12:15"  # 10:05 plus two hours, rounded up to the next slot


def test_is_available(service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10))

    assert availability.is_available(service, staff, at(monday, 14))
    assert not availability.is_available(service, staff, at(monday, 10, 15))
    assert not availability.is_available(service, staff, at(monday, 14, 5))  # not on the grid


def test_cancelled_bookings_do_not_block(service, staff):
    monday = next_weekday(0)
    make_booking(service, staff, at(monday, 10), status=Booking.Status.CANCELLED)

    assert availability.is_available(service, staff, at(monday, 10))


def test_unconfirmed_bookings_block_until_their_hold_runs_out(service, staff):
    monday = next_weekday(0)
    now = timezone.now()
    booking = make_booking(
        service,
        staff,
        at(monday, 10),
        status=Booking.Status.PENDING,
        hold_expires_at=now + timedelta(minutes=10),
    )

    assert not availability.is_available(service, staff, at(monday, 10), now=now)
    assert availability.is_available(
        service, staff, at(monday, 10), now=booking.hold_expires_at + timedelta(seconds=1)
    )


def test_inactive_staff_are_not_offered(service, staff):
    staff.is_active = False
    staff.save()

    assert list(availability.bookable_staff(service)) == []
    assert availability.available_slots(service, next_weekday(0)) == []


def test_booking_window_starts_on_the_business_s_local_date(business):
    business.timezone = "Pacific/Auckland"
    business.min_notice_minutes = 0
    now = datetime(2026, 1, 12, 20, 0, tzinfo=UTC)  # already Tuesday morning in Auckland

    first_day, last_day, earliest = availability.booking_window(business, now)

    assert first_day == date(2026, 1, 13)
    assert last_day == date(2026, 1, 13) + timedelta(days=business.max_advance_days)
    assert earliest == now
