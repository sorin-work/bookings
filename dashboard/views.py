from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from appointments import services
from appointments.models import Booking
from businesses.decorators import business_required

from . import calendar


@business_required
def home(request):
    business = request.business
    return render(request, "dashboard/home.html", {"business": business})


def _parse_day(value, default):
    return date.fromisoformat(value) if value else default


@business_required
def calendar_view(request):
    business = request.business
    day = _parse_day(request.GET.get("date"), business.today())
    view = request.GET.get("view") if request.GET.get("view") in ("day", "week") else "day"
    staff = business.staff.prefetch_related("working_hours")
    selected_staff = None
    if request.GET.get("staff", "").isdigit():
        selected_staff = staff.filter(pk=int(request.GET["staff"])).first()
    shown = [selected_staff] if selected_staff else list(staff)
    if view == "week":
        grid = calendar.week_grid(business, day, shown)
        step = timedelta(days=7)
    else:
        grid = calendar.day_grid(business, day, shown)
        step = timedelta(days=1)
    context = {
        "grid": grid,
        "day": day,
        "view": view,
        "today": business.today(),
        "previous_day": day - step,
        "next_day": day + step,
        "staff": staff,
        "selected_staff": selected_staff,
        "week_start": calendar.week_start(day),
        "week_end": calendar.week_start(day) + timedelta(days=6),
    }
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/includes/calendar.html", context)
    return render(request, "dashboard/calendar.html", context)


def _booking(request, pk):
    return get_object_or_404(request.business.bookings.select_related("service", "staff"), pk=pk)


@business_required
def booking_detail(request, pk):
    booking = _booking(request, pk)
    context = {"booking": booking, "can_mark": booking.start <= timezone.now() and booking.is_open}
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/includes/booking_panel.html", context)
    return render(request, "dashboard/booking_detail.html", context)


def _after_action(request, booking):
    """htmx: re-render the panel and tell the calendar to refresh; otherwise redirect."""
    if request.headers.get("HX-Request"):
        response = booking_detail(request, booking.pk)
        response["HX-Trigger"] = "bookingChanged"
        return response
    return redirect("dashboard:booking", pk=booking.pk)


@business_required
@require_POST
def booking_outcome(request, pk):
    booking = _booking(request, pk)
    try:
        services.set_outcome(booking, request.POST.get("status"))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Marked as {booking.get_status_display().lower()}.")
    return _after_action(request, booking)


@business_required
@require_POST
def booking_cancel(request, pk):
    booking = _booking(request, pk)
    if booking.is_open:
        services.cancel_booking(booking, Booking.CancelledBy.BUSINESS)
        messages.success(request, "Booking cancelled. The customer has been emailed.")
    return _after_action(request, booking)
