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
        # Touching intervals don't overlap: one appointment can end at 10:00 and the
        # next start at 10:00.
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Shift:
    """Working hours on one weekday (0 = Monday), as local wall-clock times."""

    weekday: int
    start: time
    end: time


@dataclass(frozen=True)
class ServiceSpec:
    duration: timedelta
    buffer_before: timedelta = timedelta(0)
    buffer_after: timedelta = timedelta(0)


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
        window_start = datetime.combine(day, shift.start, tzinfo=tz).astimezone(UTC)
        window_end = datetime.combine(day, shift.end, tzinfo=tz).astimezone(UTC)
        start = window_start
        while True:
            end = start + service.duration
            if end > window_end:
                break
            # The buffers have to be free as well, but may run outside working hours.
            occupied = Interval(start - service.buffer_before, end + service.buffer_after)
            free = not any(occupied.overlaps(busy) for busy in schedule.busy)
            if (earliest is None or start >= earliest) and free:
                slots.append(Slot(start, end, schedule.staff_id))
            start += interval
    return slots


def days_between(first: date, last: date):
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)
