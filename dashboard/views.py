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
    view = "day"
    staff = business.staff.prefetch_related("working_hours")
    shown = list(staff)
    grid = calendar.day_grid(business, day, shown)
    step = timedelta(days=1)
    context = {
        "grid": grid,
        "day": day,
        "view": view,
        "today": business.today(),
        "previous_day": day - step,
        "next_day": day + step,
    }
    return render(request, "dashboard/calendar.html", context)
