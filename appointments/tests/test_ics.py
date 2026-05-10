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


def test_long_lines_are_folded(business, service, staff):
    business.address = "Unit 4, The Old Tannery, 112 Long Lane Industrial Estate, Little Hampton"
    booking = make_booking(service, staff, at(next_weekday(0), 10))

    body = ics.booking_ics(booking)

    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert "LOCATION:Unit 4\\, The Old Tannery" in body.replace("\r\n ", "")


def test_folding_keeps_multibyte_characters_whole():
    line = "SUMMARY:" + "é" * 60

    folded = ics._fold(line)

    assert folded.replace("\r\n ", "") == line
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
