"""Numbers for the dashboard. Days and weeks are in the business's time zone."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum

from appointments.models import Booking


def _start_of(day, tz):
    return datetime.combine(day, time(0), tzinfo=tz)


def period_totals(business, first_day, last_day):
    """Number of bookings and revenue for appointments between two days."""
    tz = business.tz
    qs = Booking.objects.filter(
        business=business,
        start__gte=_start_of(first_day, tz),
        start__lt=_start_of(last_day + timedelta(days=1), tz),
    )
    # Cancelled bookings and no-shows don't bring in money.
    totals = qs.aggregate(
        count=Count("pk", filter=~Q(status__in=Booking.CLOSED_STATUSES)),
        revenue=Sum(
            "price", filter=Q(status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED])
        ),
    )
    return {"count": totals["count"] or 0, "revenue": totals["revenue"] or 0}


def summary(business):
    today = business.today()
    monday = today - timedelta(days=today.weekday())
    first_of_month = today.replace(day=1)
    next_month = (first_of_month + timedelta(days=32)).replace(day=1)
    return {
        "today": period_totals(business, today, today),
        "week": period_totals(business, monday, monday + timedelta(days=6)),
        "month": period_totals(business, first_of_month, next_month - timedelta(days=1)),
    }


def outcome_rates(business, days=30):
    """Share of bookings in the last `days` days that were cancelled or no-shows."""
    tz = business.tz
    today = business.today()
    qs = Booking.objects.filter(
        business=business,
        start__gte=_start_of(today - timedelta(days=days), tz),
        start__lt=_start_of(today, tz),
    ).exclude(status=Booking.Status.EXPIRED)
    counts = dict(qs.values_list("status").annotate(n=Count("pk")))
    total = sum(counts.values())

    def share(status):
        if not total:
            return None
        return (Decimal(counts.get(status, 0)) * 100 / total).quantize(Decimal("1"))

    return {
        "total": total,
        "cancelled": share(Booking.Status.CANCELLED),
        "no_show": share(Booking.Status.NO_SHOW),
    }


def top_services(business, days=90, limit=5):
    today = business.today()
    qs = Booking.objects.filter(
        business=business,
        start__gte=_start_of(today - timedelta(days=days), business.tz),
    ).exclude(status__in=Booking.CLOSED_STATUSES)
    return list(
        qs.values("service__name")
        .annotate(count=Count("pk"))
        .order_by("-count", "service__name")[:limit]
    )
