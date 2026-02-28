from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import User
from businesses.models import Business, Service

pytestmark = pytest.mark.django_db


def service_data(**overrides):
    data = {
        "name": "Colour",
        "description": "",
        "duration_minutes": 90,
        "price": "70.00",
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 10,
    }
    data.update(overrides)
    return data


def test_add_a_service(owner_client, business):
    response = owner_client.post(reverse("businesses:service_new"), service_data())

    assert response.status_code == 302
    service = business.services.get()
    assert service.name == "Colour"
    assert service.duration_minutes == 90
    assert service.price == Decimal("70.00")
    assert service.buffer_after_minutes == 10


@pytest.mark.parametrize(
    "field, value",
    [("duration_minutes", 0), ("duration_minutes", 13 * 60), ("price", "-1"), ("name", "")],
)
def test_invalid_services_are_rejected(owner_client, business, field, value):
    response = owner_client.post(reverse("businesses:service_new"), service_data(**{field: value}))

    assert response.status_code == 200
    assert not business.services.exists()


def test_edit_a_service(owner_client, service):
    response = owner_client.post(
        reverse("businesses:service_edit", args=[service.pk]), service_data(name="Long colour")
    )

    assert response.status_code == 302
    service.refresh_from_db()
    assert service.name == "Long colour"


def test_cannot_edit_another_business_s_service(owner_client):
    other = User.objects.create_user(email="other@example.com", password="x")
    business = Business.objects.create(owner=other, name="Other", slug="other")
    theirs = Service.objects.create(business=business, name="Theirs", duration_minutes=30, price=1)

    response = owner_client.get(reverse("businesses:service_edit", args=[theirs.pk]))

    assert response.status_code == 404


def test_archive_and_restore(owner_client, service):
    owner_client.post(reverse("businesses:service_archive", args=[service.pk]))
    service.refresh_from_db()
    assert not service.is_active

    owner_client.post(reverse("businesses:service_archive", args=[service.pk]))
    service.refresh_from_db()
    assert service.is_active


def test_move_a_service_up(owner_client, business, service):
    second = Service.objects.create(
        business=business, name="Beard trim", duration_minutes=15, price=10, position=1
    )
    service.position = 0
    service.save()

    owner_client.post(reverse("businesses:service_move", args=[second.pk, "up"]))

    assert list(business.services.all()) == [second, service]
