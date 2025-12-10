"""Public pages: the booking page of each business and the customer's booking link."""

from datetime import date, timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business, StaffMember
from scheduling import availability


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
    """The staff member from ?staff=, or the first one who offers the service."""
    staff_id = request.GET.get("staff") or request.POST.get("staff")
    staff_qs = availability.bookable_staff(service)
    if not staff_id:
        member = staff_qs.first()
        if member is None:
            raise Http404("Nobody offers this service yet.")
        return member
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
    times = [slot.start for slot in slots]
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
        **_times(service, staff, day),
    }
    return render(request, "appointments/includes/slots.html", context)
