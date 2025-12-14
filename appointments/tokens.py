"""Signed links that let customers manage a booking without an account."""

from django.conf import settings
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

# The same booking always gets the same link, so links in older emails keep working.
signer = signing.Signer(salt="appointments.manage")


def make_token(booking):
    return signer.sign(str(booking.public_id))


def manage_path(booking):
    return reverse("appointments:manage", args=[make_token(booking)])


def absolute_url(path):
    return f"{settings.SITE_URL}{path}"


def booking_for_token(token):
    from .models import Booking

    try:
        public_id = signer.unsign(token)
    except signing.BadSignature as exc:
        raise Http404("This booking link isn't valid.") from exc
    return get_object_or_404(
        Booking.objects.select_related("business", "service", "staff"), public_id=public_id
    )
