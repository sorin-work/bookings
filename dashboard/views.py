from datetime import date, timedelta

from django.shortcuts import render

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
    shown = list(staff)
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
        "week_start": calendar.week_start(day),
        "week_end": calendar.week_start(day) + timedelta(days=6),
    }
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/includes/calendar.html", context)
    return render(request, "dashboard/calendar.html", context)
