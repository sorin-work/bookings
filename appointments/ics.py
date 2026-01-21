"""Minimal iCalendar (RFC 5545) output for bookings."""

from datetime import UTC

from django.utils import timezone

from .tokens import absolute_url


def _escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _stamp(value):
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def event_lines(booking, *, include_customer=False):
    business = booking.business
    summary = f"{booking.service.name} at {business.name}"
    description = [f"Booking reference: {booking.reference}", f"With: {booking.staff.name}"]
    if include_customer:
        summary = f"{booking.service.name}: {booking.customer_name}"
        description = [
            f"Reference: {booking.reference}",
            f"Customer: {booking.customer_name}",
            f"Phone: {booking.customer_phone}",
            f"Email: {booking.customer_email}",
        ]
    else:
        description.append(f"Manage your booking: {absolute_url(booking.manage_url)}")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{booking.public_id}@bookings",
        f"DTSTAMP:{_stamp(timezone.now())}",
        f"DTSTART:{_stamp(booking.start)}",
        f"DTEND:{_stamp(booking.end)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(chr(10).join(description))}",
    ]
    if business.address:
        lines.append(f"LOCATION:{_escape(business.address)}")
    if booking.status in booking.CLOSED_STATUSES:
        lines.append("STATUS:CANCELLED")
    else:
        lines.append("STATUS:CONFIRMED")
    lines.append("END:VEVENT")
    return lines


def calendar(events, *, method="PUBLISH", name=None):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//bookings//EN", f"METHOD:{method}"]
    if name:
        lines.append(f"X-WR-CALNAME:{_escape(name)}")
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def booking_ics(booking):
    return calendar([event_lines(booking)])
