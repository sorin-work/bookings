from datetime import time

import pytest
from django.db import IntegrityError
from django.urls import reverse

from businesses.models import WorkingHours

pytestmark = pytest.mark.django_db


def hours_data(**values):
    data = {f"d{d}_{s}_{p}": "" for d in range(7) for s in (1, 2) for p in ("start", "end")}
    data.update(values)
    return data


def test_save_working_hours(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_hours", args=[staff.pk]),
        hours_data(d0_1_start="09:00", d0_1_end="12:00", d0_2_start="13:00", d0_2_end="17:30"),
    )

    assert response.status_code == 302
    rows = list(staff.working_hours.values_list("weekday", "start_time", "end_time"))
    assert rows == [(0, time(9), time(12)), (0, time(13), time(17, 30))]


def test_working_hours_must_end_after_they_start(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_hours", args=[staff.pk]),
        hours_data(d2_1_start="17:00", d2_1_end="09:00"),
    )

    assert response.status_code == 200
    assert "Must be after the start time." in response.content.decode()
    assert staff.working_hours.count() == 5  # unchanged


def test_database_rejects_backwards_working_hours(staff):
    with pytest.raises(IntegrityError):
        WorkingHours.objects.create(staff=staff, weekday=6, start_time=time(18), end_time=time(8))


def test_shifts_on_one_day_cannot_overlap(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_hours", args=[staff.pk]),
        hours_data(d0_1_start="09:00", d0_1_end="13:00", d0_2_start="12:00", d0_2_end="17:00"),
    )

    assert response.status_code == 200
    assert "Overlaps the shift before it." in response.content.decode()


def test_add_a_staff_member_who_offers_a_service(owner_client, business, service):
    response = owner_client.post(
        reverse("businesses:staff_new"),
        {
            "name": "Sam",
            "email": "",
            "services": [service.pk],
            "color": "#16a34a",
            "is_active": "on",
        },
    )

    member = business.staff.get(name="Sam")
    assert response.status_code == 302
    assert response["Location"] == reverse("businesses:staff_hours", args=[member.pk])
    assert list(member.services.all()) == [service]


def test_half_filled_shift_is_rejected(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_hours", args=[staff.pk]), hours_data(d4_1_start="09:00")
    )

    assert response.status_code == 200
    assert "Enter both times." in response.content.decode()


def test_copy_monday_fills_in_the_week_without_saving(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_hours", args=[staff.pk]),
        hours_data(d0_1_start="08:00", d0_1_end="16:00", copy="1"),
    )

    assert response.status_code == 200
    form = response.context["form"]
    assert form["d3_1_start"].value() == "08:00"
    assert form["d5_1_start"].value() == ""
    assert staff.working_hours.filter(start_time=time(8)).count() == 0


def test_add_whole_days_off(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_time_off", args=[staff.pk]),
        {"start_date": "2030-07-01", "end_date": "2030-07-05", "reason": "Holiday"},
    )

    assert response.status_code == 302
    item = staff.time_off.get()
    assert item.start.isoformat() == "2030-06-30T23:00:00+00:00"  # midnight in London (BST)
    assert item.end.isoformat() == "2030-07-05T23:00:00+00:00"
    assert item.reason == "Holiday"


def test_time_off_must_end_after_it_starts(owner_client, staff):
    response = owner_client.post(
        reverse("businesses:staff_time_off", args=[staff.pk]),
        {
            "start_date": "2030-07-05",
            "start_time": "14:00",
            "end_date": "2030-07-05",
            "end_time": "13:00",
        },
    )

    assert response.status_code == 200
    assert not staff.time_off.exists()


def test_remove_time_off(owner_client, staff):
    owner_client.post(
        reverse("businesses:staff_time_off", args=[staff.pk]),
        {"start_date": "2030-07-01", "end_date": "2030-07-01"},
    )
    item = staff.time_off.get()

    owner_client.post(reverse("businesses:staff_time_off_delete", args=[staff.pk, item.pk]))

    assert not staff.time_off.exists()
