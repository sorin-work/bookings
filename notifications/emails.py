"""Emails to customers, the business and its staff about bookings.

Each message has a plain text template under templates/emails/ and is rendered
in the business's time zone.
"""

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

from appointments.tokens import absolute_url

CUSTOMER_SUBJECTS = {
    "created": "Booking confirmed: {service} on {when}",
    "cancelled": "Booking cancelled: {service} on {when}",
    "rescheduled": "Booking moved: {service} is now on {when}",
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
    return subject


def _send(name, booking, to, subject, *, reply_to=None, **extra):
    context = _context(booking, **extra)
    with timezone.override(booking.business.tz):
        body = render_to_string(f"emails/{name}.txt", context)
    message = EmailMessage(
        subject=_subject(subject, booking),
        body=body,
        to=to,
        reply_to=reply_to,
    )
    message.send()


def _customer(kind, booking, **extra):
    _send(
        f"customer_{kind}",
        booking,
        [booking.customer_email],
        CUSTOMER_SUBJECTS[kind],
        **extra,
    )


def booking_created(booking):
    _customer("created", booking)


def booking_cancelled(booking):
    _customer("cancelled", booking)


def booking_rescheduled(booking, old_start):
    _customer("rescheduled", booking, old_start=old_start)
