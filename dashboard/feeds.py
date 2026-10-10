"""Private iCalendar feed per staff member, for subscribing from a phone."""

from datetime import timedelta

from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from appointments.ics import calendar, event_lines
from appointments.models import Booking
from appointments.tokens import absolute_url
from businesses.models import StaffMember

signer = signing.Signer(salt="dashboard.staff-feed")


def feed_token(member):
    return signer.sign(str(member.pk)).split(":", 1)[1]


def feed_url(member):
    return absolute_url(reverse("dashboard:staff_feed", args=[member.pk, feed_token(member)]))


def staff_feed(request, pk, token):
    try:
        signer.unsign(f"{pk}:{token}")
    except signing.BadSignature as exc:
        raise Http404("Unknown calendar.") from exc
    member = get_object_or_404(StaffMember.objects.select_related("business"), pk=pk)
    now = timezone.now()
    bookings = (
        member.bookings.filter(
            start__gte=now - timedelta(days=30), start__lte=now + timedelta(days=180)
        )
        .exclude(status__in=Booking.CLOSED_STATUSES)
        .select_related("business", "service", "staff")
    )
    body = calendar(
        [event_lines(booking, include_customer=True) for booking in bookings],
        name=f"{member.name} · {member.business.name}",
    )
    return HttpResponse(body, content_type="text/calendar; charset=utf-8")
