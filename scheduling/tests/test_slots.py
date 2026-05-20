from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

from scheduling.slots import Interval, ServiceSpec, Shift, StaffSchedule, staff_slots
from testutils import LONDON, at

MONDAY = date(2026, 1, 12)
HOUR = timedelta(hours=1)
HALF_HOUR = timedelta(minutes=30)


def starts(slots):
    return [slot.start.astimezone(LONDON).strftime("%H:%M") for slot in slots]


def schedule(*shifts, busy=()):
    return StaffSchedule(staff_id=1, shifts=list(shifts), busy=list(busy))


def test_slots_step_through_the_shift():
    slots = staff_slots(
        schedule(Shift(0, time(9), time(12))), ServiceSpec(HOUR), MONDAY, LONDON, interval=HALF_HOUR
    )

    assert starts(slots)[:4] == ["09:00", "09:30", "10:00", "10:30"]
    assert all(slot.end - slot.start == HOUR for slot in slots)
    assert all(slot.end <= at(MONDAY, 12) for slot in slots)
    assert all(slot.staff_id == 1 for slot in slots)


def test_no_slots_on_days_off():
    slots = staff_slots(
        schedule(Shift(1, time(9), time(17))), ServiceSpec(HOUR), MONDAY, LONDON, interval=HALF_HOUR
    )

    assert slots == []


def test_split_shift_has_no_slots_in_the_break():
    slots = staff_slots(
        schedule(Shift(0, time(9), time(11)), Shift(0, time(14), time(16))),
        ServiceSpec(HOUR),
        MONDAY,
        LONDON,
        interval=HOUR,
    )

    assert "12:00" not in starts(slots)
    assert starts(slots)[0] == "09:00"
    assert "14:00" in starts(slots)


def test_service_longer_than_the_shift_has_no_slots():
    slots = staff_slots(
        schedule(Shift(0, time(9), time(10))),
        ServiceSpec(timedelta(hours=2)),
        MONDAY,
        LONDON,
        interval=HALF_HOUR,
    )

    assert slots == []


def test_time_off_blocks_slots():
    off = Interval(at(MONDAY, 10), at(MONDAY, 12))
    slots = staff_slots(
        schedule(Shift(0, time(9), time(14)), busy=[off]),
        ServiceSpec(HOUR),
        MONDAY,
        LONDON,
        interval=HALF_HOUR,
    )

    assert "09:30" not in starts(slots)
    assert "10:00" not in starts(slots)
    assert "11:30" not in starts(slots)
    assert "12:30" in starts(slots)


def test_nothing_before_the_earliest_start():
    slots = staff_slots(
        schedule(Shift(0, time(9), time(17))),
        ServiceSpec(HOUR),
        MONDAY,
        LONDON,
        interval=HALF_HOUR,
        earliest=at(MONDAY, 13, 10),
    )

    assert starts(slots)[0] == "13:30"


def test_buffers_keep_a_gap_after_other_bookings():
    # A booking 10:00-11:00 with 15 minutes to clean up afterwards.
    booked = Interval(at(MONDAY, 10), at(MONDAY, 11, 15))
    slots = staff_slots(
        schedule(Shift(0, time(9), time(13)), busy=[booked]),
        ServiceSpec(HALF_HOUR),
        MONDAY,
        LONDON,
        interval=timedelta(minutes=15),
    )

    assert "11:00" not in starts(slots)
    assert "11:30" in starts(slots)


def test_own_buffers_must_be_free_too():
    booked = Interval(at(MONDAY, 11), at(MONDAY, 12))
    spec = ServiceSpec(HALF_HOUR, buffer_before=timedelta(minutes=15), buffer_after=HALF_HOUR)
    slots = staff_slots(
        schedule(Shift(0, time(9), time(14)), busy=[booked]),
        spec,
        MONDAY,
        LONDON,
        interval=timedelta(minutes=15),
    )

    # 09:45 sets up from 09:30 and cleans up until 10:45, before the booking.
    assert "09:45" in starts(slots)
    # 10:15 would clean up until 11:15, into the booking.
    assert "10:15" not in starts(slots)
    # 12:00 needs 11:45 to set up, during the booking.
    assert "12:00" not in starts(slots)
    assert "12:30" in starts(slots)


def test_buffer_may_run_past_the_end_of_the_shift():
    spec = ServiceSpec(HALF_HOUR, buffer_after=HALF_HOUR)
    slots = staff_slots(
        schedule(Shift(0, time(9), time(10))), spec, MONDAY, LONDON, interval=HALF_HOUR
    )

    assert starts(slots)[0] == "09:00"


def test_back_to_back_appointments_are_allowed():
    booked = Interval(at(MONDAY, 10), at(MONDAY, 11))
    slots = staff_slots(
        schedule(Shift(0, time(9), time(13)), busy=[booked]),
        ServiceSpec(HOUR),
        MONDAY,
        LONDON,
        interval=HOUR,
    )

    assert starts(slots)[:2] == ["09:00", "11:00"]


def test_touching_intervals_do_not_overlap():
    first = Interval(at(MONDAY, 9), at(MONDAY, 10))

    assert not first.overlaps(Interval(at(MONDAY, 10), at(MONDAY, 11)))
    assert first.overlaps(Interval(at(MONDAY, 9, 59), at(MONDAY, 11)))


def test_slots_keep_wall_clock_times_after_the_clocks_go_forward():
    # Looking at the Monday after British Summer Time starts (29 March 2026)
    # from a week before it.
    day = date(2026, 3, 30)
    slots = staff_slots(
        schedule(Shift(0, time(9), time(11))),
        ServiceSpec(HOUR),
        day,
        LONDON,
        interval=HOUR,
        earliest=at(date(2026, 3, 20), 12),
    )

    assert slots[0].start.astimezone(LONDON).isoformat() == "2026-03-30T09:00:00+01:00"
    assert starts(slots)[0] == "09:00"


def test_slots_for_a_business_west_of_utc_after_the_clocks_go_back():
    new_york = ZoneInfo("America/New_York")
    day = date(2026, 11, 2)  # US daylight saving time ended on 1 November
    slots = staff_slots(
        schedule(Shift(0, time(9), time(11))),
        ServiceSpec(HOUR),
        day,
        new_york,
        interval=HOUR,
        earliest=at(date(2026, 10, 20), 9, tz=new_york),
    )

    assert slots[0].start.isoformat() == "2026-11-02T14:00:00+00:00"


def test_slot_may_end_exactly_at_closing_time():
    slots = staff_slots(
        schedule(Shift(0, time(9), time(12))), ServiceSpec(HOUR), MONDAY, LONDON, interval=HALF_HOUR
    )

    assert starts(slots) == ["09:00", "09:30", "10:00", "10:30", "11:00"]
