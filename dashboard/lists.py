"""Bookings and customers lists."""

from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.shortcuts import render

from appointments.models import Booking
from businesses.decorators import business_required


def _parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def filtered_bookings(request):
    """The business's bookings narrowed down by the query string filters."""
    business = request.business
    tz = business.tz
    qs = business.bookings.select_related("service", "staff")
    filters = {
        "status": request.GET.get("status", ""),
        "from": _parse_day(request.GET.get("from")),
        "to": _parse_day(request.GET.get("to")),
        "staff": request.GET.get("staff", ""),
        "q": request.GET.get("q", "").strip(),
    }
    if filters["status"] in Booking.Status.values:
        qs = qs.filter(status=filters["status"])
    if filters["from"]:
        qs = qs.filter(start__gte=datetime.combine(filters["from"], time(0), tzinfo=tz))
    if filters["to"]:
        end = datetime.combine(filters["to"] + timedelta(days=1), time(0), tzinfo=tz)
        qs = qs.filter(start__lt=end)
    if filters["staff"].isdigit():
        qs = qs.filter(staff_id=int(filters["staff"]))
    if filters["q"]:
        q = filters["q"]
        qs = qs.filter(
            Q(customer_name__icontains=q)
            | Q(customer_email__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(reference__iexact=q)
        )
    if not filters["from"] and not filters["to"]:
        # Newest first when browsing everything.
        qs = qs.order_by("-start")
    return qs, filters


@business_required
def bookings(request):
    qs, filters = filtered_bookings(request)
    context = {"bookings": qs[:200], "filters": filters}
    context["statuses"] = Booking.Status.choices
    context["staff"] = request.business.staff.all()
    return render(request, "dashboard/bookings.html", context)
