import pytest
from django.urls import reverse

from accounts.models import User
from appointments.models import Booking
from appointments.services import Customer, create_booking
from businesses.models import Business, Service, StaffMember
from conftest import PASSWORD
from testutils import at, next_weekday

pytestmark = pytest.mark.django_db


def test_deleting_the_account_removes_the_business_and_its_bookings(owner_client, staff, service):
    create_booking(
        service, at(next_weekday(1), 10), Customer("Ana", "ana@example.com", "0123456789")
    )

    response = owner_client.post(
        reverse("accounts:delete"), {"password": PASSWORD, "confirm": "on"}
    )

    assert response.status_code == 302
    assert not User.objects.exists()
    assert not Business.objects.exists()
    assert not Service.objects.exists()
    assert not StaffMember.objects.exists()
    assert not Booking.objects.exists()


def test_deleting_needs_the_password(owner_client, user):
    response = owner_client.post(reverse("accounts:delete"), {"password": "wrong", "confirm": "on"})

    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()
