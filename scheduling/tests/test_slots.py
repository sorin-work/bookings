from datetime import date, time, timedelta

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
