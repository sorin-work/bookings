"""Emails to customers, the business and its staff about bookings.

Each message has a plain text template under templates/emails/ and is rendered
in the business's time zone.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import timezone

from appointments.ics import booking_ics
from appointments.tokens import absolute_url

logger = logging.getLogger(__name__)

CUSTOMER_SUBJECTS = {
    "created": "Booking confirmed: {service} on {when}",
    "cancelled": "Booking cancelled: {service} on {when}",
    "rescheduled": "Booking moved: {service} is now on {when}",
    "pending": "Please confirm your booking: {service} on {when}",
    "confirmed": "Booking confirmed: {service} on {when}",
    "reminder": "Reminder: {service} on {when}",
}

BUSINESS_SUBJECTS = {
    "created": "New booking: {customer}, {service} on {when}",
    "cancelled": "Cancelled: {customer}, {service} on {when}",
    "rescheduled": "Moved: {customer}, {service} now on {when}",
    "pending": "New booking (waiting for confirmation): {customer}, {service} on {when}",
    "confirmed": "Confirmed: {customer}, {service} on {when}",
}


def _context(booking, **extra):
    return {
        "booking": booking,
        "business": booking.business,
        "manage_url": absolute_url(booking.manage_url),
        "site_url": settings.SITE_URL,
        **extra,
    }


def _subject(template, booking):
    when = booking.start.astimezone(booking.business.tz)
    subject = template.format(
        service=booking.service.name,
        customer=booking.customer_name,
        when=f"{when:%a %d %b} at {when:%H:%M}",
    )
    # Header values can't contain line breaks; Django refuses to send them.
    return " ".join(subject.split())


def _send(name, booking, to, subject, *, reply_to=None, attach_ics=False, **extra):
    context = _context(booking, **extra)
    with timezone.override(booking.business.tz):
        body = render_to_string(f"emails/{name}.txt", context)
        try:
            html = render_to_string(f"emails/{name}.html", context)
        except TemplateDoesNotExist:
            html = None
    message = EmailMultiAlternatives(
        subject=_subject(subject, booking),
        body=body,
        to=to,
        reply_to=reply_to,
    )
    if html:
        message.attach_alternative(html, "text/html")
    if attach_ics:
        message.attach(f"booking-{booking.reference}.ics", booking_ics(booking), "text/calendar")
    try:
        message.send()
    except Exception:
        # A mail server hiccup shouldn't undo or break the booking itself.
        logger.exception("Could not send %s email for booking %s", name, booking.reference)


def _customer(kind, booking, *, attach_ics=False, **extra):
    _send(
        f"customer_{kind}",
        booking,
        [booking.customer_email],
        CUSTOMER_SUBJECTS[kind],
        reply_to=[booking.business.notification_email],
        attach_ics=attach_ics,
        **extra,
    )


def _business_recipients(booking):
    recipients = [booking.business.notification_email]
    staff_email = booking.staff.email
    if staff_email and staff_email.lower() not in {r.lower() for r in recipients}:
        recipients.append(staff_email)
    return recipients


def _business(kind, booking, **extra):
    _send(
        f"business_{kind}",
        booking,
        _business_recipients(booking),
        BUSINESS_SUBJECTS[kind],
        reply_to=[booking.customer_email],
        **extra,
    )


def booking_created(booking):
    if booking.status == booking.Status.PENDING:
        _customer("pending", booking)
    else:
        _customer("created", booking, attach_ics=True)
    if booking.source == booking.Source.ONLINE:
        _business("pending" if booking.status == booking.Status.PENDING else "created", booking)


def booking_cancelled(booking):
    _customer("cancelled", booking)
    if booking.cancelled_by == booking.CancelledBy.CUSTOMER:
        _business("cancelled", booking)


def booking_rescheduled(booking, old_start):
    _customer("rescheduled", booking, attach_ics=True, old_start=old_start)
    _business("rescheduled", booking, old_start=old_start)


def booking_confirmed(booking):
    _customer("confirmed", booking, attach_ics=True)
    _business("confirmed", booking)


def booking_reminder(booking):
    _customer("reminder", booking)
