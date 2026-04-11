"""Public pages: the booking page of each business and the customer's booking link."""

from datetime import date, datetime, timedelta

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from businesses.models import Business, StaffMember
from scheduling import availability

from . import services
from .forms import CustomerForm
from .models import Booking
from .tokens import booking_for_token


def _business(slug):
    business = get_object_or_404(Business, slug=slug)
    # Customers see times in the business's time zone, wherever they are.
    timezone.activate(business.tz)
    return business


def _public_services(business):
    services_qs = business.services.filter(is_active=True)
    return services_qs


def business_page(request, slug):
    business = _business(slug)
    offered = [s for s in _public_services(business) if availability.bookable_staff(s).exists()]
    context = {"business": business, "services": offered}
    return render(request, "appointments/business.html", context)


def _service(business, service_id):
    return get_object_or_404(_public_services(business), pk=service_id)


def _staff(request, business, service):
    """The staff member from ?staff=, or None for "anyone available"."""
    staff_id = request.GET.get("staff") or request.POST.get("staff")
    if not staff_id:
        return None
    staff_qs = availability.bookable_staff(service)
    try:
        return staff_qs.get(pk=int(staff_id))
    except (ValueError, StaffMember.DoesNotExist) as exc:
        raise Http404("Unknown staff member.") from exc


def _parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _picker(service, staff, selected=None):
    """Context for the date strip and the times of the selected day."""
    days = list(availability.available_days(service, staff=staff).items())
    free_days = [day for day, free in days if free]
    if selected is None or not any(day == selected for day, _ in days):
        selected = free_days[0] if free_days else days[0][0]
    return {
        "days": days,
        "selected": selected,
        "has_free_days": bool(free_days),
        **_times(service, staff, selected),
    }


def _times(service, staff, day):
    slots = availability.available_slots(service, day, staff=staff)
    times = [slot.start for slot in slots] if staff else availability.start_times(slots)
    return {"day": day, "times": times}


def service_page(request, slug, service_id):
    business = _business(slug)
    service = _service(business, service_id)
    staff = _staff(request, business, service)
    context = {
        "business": business,
        "service": service,
        "staff": staff,
        "staff_options": availability.bookable_staff(service),
        "slots_url": reverse("appointments:slots", args=[business.slug, service.pk]),
        "book_url": reverse("appointments:book", args=[business.slug, service.pk]),
        **_picker(service, staff, _parse_day(request.GET.get("date"))),
    }
    return render(request, "appointments/service.html", context)


def slots(request, slug, service_id):
    """htmx partial: the free times on one day."""
    business = _business(slug)
    service = _service(business, service_id)
    staff = _staff(request, business, service)
    day = _parse_day(request.GET.get("date"))
    if day is None:
        raise Http404("Pick a day.")
    context = {
        "business": business,
        "service": service,
        "staff": staff,
        "book_url": reverse("appointments:book", args=[business.slug, service.pk]),
        **_times(service, staff, day),
    }
    return render(request, "appointments/includes/slots.html", context)


def _parse_start(value):
    try:
        start = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise Http404("Pick a time.") from exc
    if start.tzinfo is None:
        raise Http404("Pick a time.")
    return start


def _is_free(service, staff, start):
    if staff is not None:
        return availability.is_available(service, staff, start)
    return bool(services.free_staff(service, start))


def book(request, slug, service_id):
    business = _business(slug)
    service = _service(business, service_id)
    staff = _staff(request, business, service)
    start = _parse_start(request.GET.get("start") or request.POST.get("start"))
    back_url = reverse("appointments:service", args=[business.slug, service.pk])
    back_url += f"?date={start.astimezone(business.tz).date().isoformat()}"
    if staff:
        back_url += f"&staff={staff.pk}"
    if not _is_free(service, staff, start):
        messages.error(request, "Sorry, that time isn't free any more. Please pick another.")
        return redirect(back_url)

    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            booking = services.create_booking(service, start, form.customer(), staff)
        except services.SlotUnavailable:
            messages.error(
                request, "Sorry, someone booked that time a moment ago. Please pick another."
            )
            return redirect(back_url)
        return redirect(f"{booking.manage_url}?new=1")
    context = {
        "business": business,
        "service": service,
        "staff": staff,
        "start": start,
        "end": start + timedelta(minutes=service.duration_minutes),
        "form": form,
        "back_url": back_url,
    }
    return render(request, "appointments/book.html", context)


def _booking(token):
    booking = booking_for_token(token)
    timezone.activate(booking.business.tz)
    return booking


def manage(request, token):
    booking = _booking(token)
    context = {
        "booking": booking,
        "business": booking.business,
        "token": token,
        "is_new": request.GET.get("new") == "1",
        "can_change": booking.customer_can_change(),
    }
    return render(request, "appointments/manage.html", context)


@require_POST
def manage_cancel(request, token):
    booking = _booking(token)
    if booking.is_open and not booking.customer_can_change():
        messages.error(
            request,
            f"It's too close to the appointment to cancel online. "
            f"Please contact {booking.business.name}.",
        )
        return redirect(booking.manage_url)
    if booking.is_open:
        services.cancel_booking(booking, Booking.CancelledBy.CUSTOMER)
        messages.success(request, "Your booking is cancelled.")
    return redirect(booking.manage_url)


def manage_reschedule(request, token):
    booking = _booking(token)
    if not booking.customer_can_change():
        if booking.is_open:
            messages.error(
                request,
                f"It's too close to the appointment to change it online. "
                f"Please contact {booking.business.name}.",
            )
        else:
            messages.error(request, "This booking can't be changed any more.")
        return redirect(booking.manage_url)
    if request.method == "POST":
        start = _parse_start(request.POST.get("start"))
        try:
            services.reschedule_booking(booking, start)
        except services.SlotUnavailable:
            messages.error(request, "Sorry, that time isn't free any more. Please pick another.")
        except services.BookingClosed:
            messages.error(request, "This booking can't be changed any more.")
            return redirect(booking.manage_url)
        else:
            messages.success(request, "Your booking has been moved.")
            return redirect(booking.manage_url)
    context = {
        "booking": booking,
        "business": booking.business,
        "service": booking.service,
        "staff": booking.staff,
        "token": token,
        "slots_url": reverse("appointments:manage_reschedule_slots", args=[token]),
        **_picker(booking.service, booking.staff, _parse_day(request.GET.get("date"))),
    }
    return render(request, "appointments/reschedule.html", context)


def manage_reschedule_slots(request, token):
    booking = _booking(token)
    day = _parse_day(request.GET.get("date"))
    if day is None:
        raise Http404("Pick a day.")
    context = {
        "booking": booking,
        "business": booking.business,
        "token": token,
        "reschedule": True,
        **_times(booking.service, booking.staff, day),
    }
    return render(request, "appointments/includes/slots.html", context)


@require_POST
def manage_confirm(request, token):
    booking = _booking(token)
    try:
        services.confirm_booking(booking)
    except services.SlotUnavailable:
        messages.error(
            request,
            "Sorry, the confirmation link ran out and someone else has booked that time since. "
            "Please pick a new time.",
        )
        return redirect(booking.manage_url)
    messages.success(request, "Thanks, your booking is confirmed.")
    return redirect(booking.manage_url)
