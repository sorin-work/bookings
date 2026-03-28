from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from appointments.models import Booking
from businesses.models import Service
from dashboard import stats
from testutils import make_booking

pytestmark = pytest.mark.django_db


def today_at(business, hour, days=0):
    day = business.today() + timedelta(days=days)
    return datetime.combine(day, time(hour), tzinfo=business.tz)


def test_dashboard_shows_today_and_what_is_next(owner_client, business, service, staff):
    make_booking(service, staff, today_at(business, 23), customer_name="Late Lou")
    make_booking(service, staff, today_at(business, 10, days=2), customer_name="Next Ned")

    response = owner_client.get(reverse("dashboard:home"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Late Lou" in content
    assert "Next Ned" in content


def test_period_totals(business, service, staff):
    make_booking(service, staff, today_at(business, 9))
    make_booking(service, staff, today_at(business, 11), price=Decimal("50.00"))
    make_booking(service, staff, today_at(business, 10, days=-40))

    totals = stats.period_totals(business, business.today(), business.today())

    assert totals == {"count": 2, "revenue": Decimal("85.00")}


def test_summary_has_today_week_and_month(business, service, staff):
    make_booking(service, staff, today_at(business, 9))

    summary = stats.summary(business)

    assert summary["today"]["count"] == 1
    assert summary["week"]["count"] >= 1
    assert summary["month"]["count"] >= 1


def test_cancelled_bookings_bring_no_revenue(business, service, staff):
    make_booking(service, staff, today_at(business, 9))
    make_booking(service, staff, today_at(business, 11), status=Booking.Status.CANCELLED)
    make_booking(service, staff, today_at(business, 13), status=Booking.Status.NO_SHOW)

    totals = stats.period_totals(business, business.today(), business.today())

    assert totals == {"count": 2, "revenue": Decimal("35.00")}


def test_outcome_rates(business, service, staff):
    for days in range(1, 9):
        make_booking(
            service, staff, today_at(business, 10, days=-days), status=Booking.Status.COMPLETED
        )
    make_booking(service, staff, today_at(business, 12, days=-3), status=Booking.Status.CANCELLED)
    make_booking(service, staff, today_at(business, 14, days=-3), status=Booking.Status.NO_SHOW)

    rates = stats.outcome_rates(business)

    assert rates == {"total": 10, "cancelled": Decimal("10"), "no_show": Decimal("10")}


def test_outcome_rates_without_bookings(business):
    assert stats.outcome_rates(business) == {"total": 0, "cancelled": None, "no_show": None}


def test_top_services(business, service, staff):
    beard = Service.objects.create(
        business=business, name="Beard trim", duration_minutes=15, price=10
    )
    for days in range(3):
        make_booking(service, staff, today_at(business, 10, days=-days))
    make_booking(beard, staff, today_at(business, 15, days=-1))

    top = stats.top_services(business)

    assert top == [
        {"service__name": "Haircut", "count": 3},
        {"service__name": "Beard trim", "count": 1},
    ]
