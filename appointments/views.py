"""Public pages: the booking page of each business and the customer's booking link."""

from datetime import date, datetime, timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business, StaffMember
from scheduling import availability

from . import services
from .forms import CustomerForm


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
    business = service.business
    first_day, _, _ = availability.booking_window(business)
    days = [(first_day + timedelta(days=i), True) for i in range(14)]
    if selected is None or not any(day == selected for day, _ in days):
        selected = first_day
    return {"days": days, "selected": selected, **_times(service, staff, selected)}


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
        return redirect(back_url)

    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            booking = services.create_booking(service, start, form.customer(), staff)
        except services.SlotUnavailable:
            return redirect(back_url)
        context = {"business": business, "booking": booking}
        return render(request, "appointments/booked.html", context)
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
