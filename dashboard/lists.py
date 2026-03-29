"""Bookings and customers lists."""

import csv
from datetime import date, datetime, time, timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
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
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "page": page,
        "bookings": page.object_list,
        "filters": filters,
        "query": query.urlencode(),
    }
    context["statuses"] = Booking.Status.choices
    context["staff"] = request.business.staff.all()
    return render(request, "dashboard/bookings.html", context)


def _cell(value):
    value = "" if value is None else str(value)
    return value


@business_required
def bookings_csv(request):
    qs, _ = filtered_bookings(request)
    tz = request.business.tz
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="bookings.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Reference",
            "Date",
            "Start",
            "End",
            "Service",
            "Staff",
            "Customer",
            "Email",
            "Phone",
            "Status",
            "Price",
        ]
    )
    for booking in qs.iterator():
        start, end = booking.start.astimezone(tz), booking.end.astimezone(tz)
        writer.writerow(
            [
                _cell(booking.reference),
                start.date().isoformat(),
                start.strftime("%H:%M"),
                end.strftime("%H:%M"),
                _cell(booking.service.name),
                _cell(booking.staff.name),
                _cell(booking.customer_name),
                _cell(booking.customer_email),
                _cell(booking.customer_phone),
                booking.get_status_display(),
                booking.price,
            ]
        )
    return response
