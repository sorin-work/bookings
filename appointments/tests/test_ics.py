from datetime import timedelta

import pytest

from appointments import ics
from testutils import at, make_booking, next_weekday

pytestmark = pytest.mark.django_db


def test_text_is_escaped():
    assert ics._escape("Cut; wash, dry\nsee you") == "Cut\\; wash\\, dry\\nsee you"


def test_event_times_are_in_utc(service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    lines = ics.event_lines(booking)

    start = booking.start.astimezone(ics.UTC)
    assert f"DTSTART:{start:%Y%m%dT%H%M%SZ}" in lines
    assert f"DTEND:{start + timedelta(minutes=45):%Y%m%dT%H%M%SZ}" in lines


def test_cancelled_bookings_are_marked_cancelled(service, staff):
    booking = make_booking(service, staff, at(next_weekday(0), 10), status="cancelled")

    assert "STATUS:CANCELLED" in ics.event_lines(booking)
