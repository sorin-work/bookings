"""Day and week grids for the staff calendar.

Bookings are placed by their position in the visible hours: `top` and `height`
are percentages of the column height.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from django.utils import timezone

from appointments.models import Booking
from businesses.models import TimeOff

DEFAULT_START_HOUR = 8
DEFAULT_END_HOUR = 18


@dataclass
class Event:
    booking: Booking
    top: float
    height: float


@dataclass
class Block:
    label: str
    top: float
    height: float


@dataclass
class Column:
    label: str
    day: object
    staff: object = None
    events: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    now_top: float | None = None


@dataclass
class Grid:
    columns: list
    start_hour: int
    end_hour: int

    @property
    def hours(self):
        return list(range(self.start_hour, self.end_hour))

    @property
    def hour_count(self):
        return self.end_hour - self.start_hour


def week_start(day):
    """The Monday of `day`'s week."""
    return day - timedelta(days=day.weekday())


def _visible_hours(staff, days, bookings, tz):
    """First and last hour to show: the working hours, or 8–18 if none are set."""
    rows = [
        row
        for member in staff
        for row in member.working_hours.all()
        if row.weekday in {day.weekday() for day in days}
    ]
    if not rows:
        start, end = DEFAULT_START_HOUR, DEFAULT_END_HOUR
    else:
        start = min(row.start_time.hour for row in rows)
        end = max(row.end_time.hour + (1 if row.end_time.minute else 0) for row in rows)
    # Bookings made outside working hours (from the dashboard) still have to show.
    for booking in bookings:
        local_start, local_end = booking.start.astimezone(tz), booking.end.astimezone(tz)
        start = min(start, local_start.hour)
        if local_end.date() > local_start.date():
            end = 24
        else:
            end = max(end, local_end.hour + (1 if local_end.minute else 0))
    return start, max(end, start + 1)


def _position(start, end, day, start_hour, end_hour, tz):
    """(top, height) in percent of the column for a period on `day`, or None if not visible."""
    grid_start = datetime.combine(day, time(start_hour), tzinfo=tz)
    if end_hour == 24:
        grid_end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz)
    else:
        grid_end = datetime.combine(day, time(end_hour), tzinfo=tz)
    start, end = max(start, grid_start), min(end, grid_end)
    if end <= start:
        return None
    total = (grid_end - grid_start).total_seconds()
    top = (start - grid_start).total_seconds() / total * 100
    height = (end - start).total_seconds() / total * 100
    return round(top, 3), round(height, 3)


def _fill(grid, business, bookings, time_off=()):
    tz = business.tz
    now = timezone.now()
    for column in grid.columns:
        for booking in bookings:
            if column.staff is not None and booking.staff_id != column.staff.pk:
                continue
            position = _position(
                booking.start, booking.end, column.day, grid.start_hour, grid.end_hour, tz
            )
            if position:
                column.events.append(Event(booking, *position))
        for item in time_off:
            if column.staff is not None and item.staff_id != column.staff.pk:
                continue
            position = _position(
                item.start, item.end, column.day, grid.start_hour, grid.end_hour, tz
            )
            if position:
                label = item.reason or "Time off"
                if column.staff is None:
                    label = f"{item.staff.name}: {label}"
                column.blocks.append(Block(label, *position))
        now_position = _position(
            now, now + timedelta(minutes=1), column.day, grid.start_hour, grid.end_hour, tz
        )
        if now_position:
            column.now_top = now_position[0]
    return grid


def _bookings(business, staff, first_day, last_day):
    tz = business.tz
    start = datetime.combine(first_day, time(0), tzinfo=tz)
    end = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=tz)
    return list(
        Booking.objects.filter(business=business, staff__in=staff, start__lt=end, end__gt=start)
        .exclude(status__in=Booking.CLOSED_STATUSES)
        .select_related("service", "staff")
        .order_by("start")
    )


def _time_off(staff, first_day, last_day, tz):
    start = datetime.combine(first_day, time(0), tzinfo=tz)
    end = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=tz)
    return list(
        TimeOff.objects.filter(staff__in=staff, start__lt=end, end__gt=start).select_related(
            "staff"
        )
    )


def day_grid(business, day, staff):
    """One column per staff member."""
    staff = list(staff)
    bookings = _bookings(business, staff, day, day)
    start_hour, end_hour = _visible_hours(staff, [day], bookings, business.tz)
    columns = [Column(label=member.name, day=day, staff=member) for member in staff]
    grid = Grid(columns, start_hour, end_hour)
    return _fill(grid, business, bookings, _time_off(staff, day, day, business.tz))


def week_grid(business, day, staff):
    """One column per day of `day`'s week, Monday first."""
    staff = list(staff)
    monday = week_start(day)
    days = [monday + timedelta(days=i) for i in range(7)]
    bookings = _bookings(business, staff, days[0], days[-1])
    start_hour, end_hour = _visible_hours(staff, days, bookings, business.tz)
    columns = [Column(label=f"{d:%a %d}", day=d) for d in days]
    grid = Grid(columns, start_hour, end_hour)
    return _fill(grid, business, bookings, _time_off(staff, days[0], days[-1], business.tz))
