from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from accounts.models import User
from appointments.models import Booking
from scheduling import availability

pytestmark = pytest.mark.django_db


def seed():
    out = StringIO()
    call_command("seed_demo", stdout=out)
    return out.getvalue()


def test_seed_creates_the_demo_account():
    output = seed()

    user = User.objects.get(email="demo@example.com")
    assert user.check_password("demo-password")
    business = user.business
    assert business.services.count() == 7
    assert business.staff.count() == 4
    assert business.bookings.count() > 300
    assert "demo@example.com / demo-password" in output


def test_seeded_bookings_do_not_overlap():
    seed()

    for staff_id in Booking.objects.values_list("staff_id", flat=True).distinct():
        bookings = list(
            Booking.objects.filter(staff_id=staff_id)
            .exclude(status__in=Booking.CLOSED_STATUSES)
            .order_by("start")
        )
        for earlier, later in zip(bookings, bookings[1:], strict=False):
            assert earlier.busy_end <= later.busy_start, (earlier, later)


def test_seeded_business_has_free_times():
    seed()
    business = User.objects.get(email="demo@example.com").business
    service = business.services.get(name="Men's cut")

    today = business.today()
    days = [today + timedelta(days=n) for n in range(1, 15)]
    free = [day for day in days if availability.available_slots(service, day)]

    assert len(free) > 5


def test_seed_twice_leaves_the_data_alone():
    seed()
    count = Booking.objects.count()

    output = seed()

    assert Booking.objects.count() == count
    assert "already exists" in output
