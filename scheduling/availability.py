"""Load schedules from the database and work out free times with `slots`."""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from appointments.models import Booking
from businesses.models import TimeOff, WorkingHours

from .slots import Interval, ServiceSpec, Shift, StaffSchedule, staff_slots


def bookable_staff(service):
    """Staff who can be booked for `service`, in a stable order."""
    return service.staff.order_by("name", "pk")


def booking_window(business, now=None):
    """(first day, last day, earliest start) customers can book, in the business's time zone."""
    now = now or timezone.now()
    today = now.date()
    last_day = today + timedelta(days=business.max_advance_days)
    earliest = now + timedelta(minutes=business.min_notice_minutes)
    return today, last_day, earliest


def service_spec(service):
    return ServiceSpec(
        duration=timedelta(minutes=service.duration_minutes),
        buffer_before=timedelta(minutes=service.buffer_before_minutes),
        buffer_after=timedelta(minutes=service.buffer_after_minutes),
    )


def load_schedules(business, staff_members, first_day, last_day):
    """A StaffSchedule per staff member with everything that blocks time between the days."""
    tz = business.tz
    # A day's slots can be blocked by bookings whose buffers reach in from either
    # side, so look a day further out in both directions.
    range_start = datetime.combine(first_day - timedelta(days=1), time(0), tzinfo=tz)
    range_end = datetime.combine(last_day + timedelta(days=2), time(0), tzinfo=tz)
    staff_ids = [member.pk for member in staff_members]

    shifts = defaultdict(list)
    for row in WorkingHours.objects.filter(staff_id__in=staff_ids):
        shifts[row.staff_id].append(Shift(row.weekday, row.start_time, row.end_time))

    busy = defaultdict(list)
    for staff_id in staff_ids:
        for booking in Booking.objects.blocking().filter(
            staff_id=staff_id, start__lt=range_end, end__gt=range_start
        ):
            busy[staff_id].append(Interval(booking.busy_start, booking.busy_end))
    time_off = TimeOff.objects.filter(
        staff_id__in=staff_ids, start__gte=range_start, start__lt=range_end
    )
    for item in time_off:
        busy[item.staff_id].append(Interval(item.start, item.end))

    return [
        StaffSchedule(staff_id=member.pk, shifts=shifts[member.pk], busy=busy[member.pk])
        for member in staff_members
    ]


def available_slots(service, day, staff=None, now=None):
    """Free slots for `service` on `day`, for one staff member or everyone who offers it.

    Sorted by start time; with several staff, the same start time shows up once per
    free staff member.
    """
    business = service.business
    now = now or timezone.now()
    first_day, last_day, earliest = booking_window(business, now)
    members = [staff] if staff else list(bookable_staff(service))
    schedules = load_schedules(business, members, day, day)
    return _slots(business, service, schedules, day, earliest)


def _slots(business, service, schedules, day, earliest):
    spec = service_spec(service)
    interval = timedelta(minutes=business.slot_interval_minutes)
    slots = []
    for schedule in schedules:
        slots.extend(
            staff_slots(schedule, spec, day, business.tz, interval=interval, earliest=earliest)
        )
    return sorted(slots, key=lambda slot: (slot.start, slot.staff_id))


def start_times(slots):
    """Distinct start times, for showing "anyone available" as one list."""
    seen = []
    for slot in slots:
        if not seen or seen[-1] != slot.start:
            seen.append(slot.start)
    return seen


def is_available(service, staff, start, now=None):
    """Whether `staff` can take `service` at exactly `start`."""
    day = start.astimezone(service.business.tz).date()
    return any(slot.start == start for slot in available_slots(service, day, staff=staff, now=now))
