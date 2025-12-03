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
