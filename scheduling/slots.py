"""Free-slot calculation.

Plain Python with no database access, so the rules are easy to test. The
availability module loads what's needed from the database and calls in here.

All datetimes going in and out are timezone-aware. Comparisons happen in UTC:
Python compares two datetimes that share a tzinfo by wall-clock time, which is
wrong across a daylight saving change.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other):
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class Shift:
    """Working hours on one weekday (0 = Monday), as local wall-clock times."""

    weekday: int
    start: time
    end: time


@dataclass(frozen=True)
class ServiceSpec:
    duration: timedelta


@dataclass
class StaffSchedule:
    staff_id: int
    shifts: list[Shift]
    busy: list[Interval] = field(default_factory=list)


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    staff_id: int


def staff_slots(schedule, service, day, tz, *, interval, earliest=None):
    """Start times on `day` (a local date) when `service` fits into `schedule`.

    `interval` is the step between offered start times, counted from the start of
    each shift. `earliest` is the first moment a slot may start (now plus the
    minimum notice).
    """
    slots = []
    for shift in schedule.shifts:
        if shift.weekday != day.weekday():
            continue
        offset = (earliest or datetime.now(UTC)).astimezone(tz).utcoffset()
        window_start = (datetime.combine(day, shift.start) - offset).replace(tzinfo=UTC)
        window_end = (datetime.combine(day, shift.end) - offset).replace(tzinfo=UTC)
        start = window_start
        while True:
            end = start + service.duration
            if end >= window_end:
                break
            if earliest is None or start >= earliest:
                slots.append(Slot(start, end, schedule.staff_id))
            start += interval
    return [slot for slot in slots if not _blocked(slot, schedule.busy)]


def _blocked(slot, busy):
    period = Interval(slot.start, slot.end)
    return any(period.overlaps(other) for other in busy)


def days_between(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)
