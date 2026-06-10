from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from appointments import services
from appointments.models import Booking
from businesses.decorators import business_required

from . import calendar, stats
from .forms import ManualBookingForm


@business_required
def home(request):
    business = request.business
    today = business.today()
    upcoming = business.bookings.upcoming().select_related("service", "staff").order_by("start")
    context = {
        "today_bookings": [b for b in upcoming[:50] if b.local_start.date() == today],
        "next_bookings": [b for b in upcoming[:50] if b.local_start.date() > today][:8],
        "summary": stats.summary(business),
        "rates": stats.outcome_rates(business),
        "top_services": stats.top_services(business),
        "booking_page_url": request.build_absolute_uri(
            reverse("appointments:business", args=[business.slug])
        ),
    }
    return render(request, "dashboard/home.html", context)


def _parse_day(value, default):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


@business_required
def calendar_view(request):
    business = request.business
    day = _parse_day(request.GET.get("date"), business.today())
    view = request.GET.get("view") if request.GET.get("view") in ("day", "week") else "day"
    staff = business.staff.filter(is_active=True).prefetch_related("working_hours")
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
    if services.cancel_booking(booking, Booking.CancelledBy.BUSINESS):
        messages.success(request, "Booking cancelled. The customer has been emailed.")
    return _after_action(request, booking)


@business_required
@require_POST
def booking_note(request, pk):
    booking = _booking(request, pk)
    booking.internal_note = request.POST.get("internal_note", "").strip()[:2000]
    booking.save(update_fields=["internal_note", "updated_at"])
    messages.success(request, "Note saved.")
    return _after_action(request, booking)


@business_required
def booking_new(request):
    business = request.business
    initial = {}
    # The calendar links here with ?staff=&date=&time= filled in.
    for key in ("staff", "date", "time", "service"):
        if request.GET.get(key):
            initial[key] = request.GET[key]
    form = ManualBookingForm(request.POST or None, business=business, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        customer = services.Customer(
            name=data["customer_name"], email=data["customer_email"], phone=data["customer_phone"]
        )
        try:
            booking = services.create_booking(
                data["service"],
                data["start"],
                customer,
                data["staff"],
                source=Booking.Source.DASHBOARD,
                override=data["override"],
            )
        except services.SlotUnavailable:
            form.add_error(
                None,
                f"{data['staff'].name} isn't free at that time. "
                "Tick the box below to book it anyway.",
            )
        else:
            messages.success(request, f"Booked {booking.customer_name} in. They've been emailed.")
            url = reverse("dashboard:calendar")
            return redirect(f"{url}?date={booking.local_start.date().isoformat()}")
    return render(request, "dashboard/booking_new.html", {"form": form})
