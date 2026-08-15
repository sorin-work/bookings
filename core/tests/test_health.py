from unittest import mock

import pytest
from django.db import OperationalError
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health_returns_ok(client):
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_an_unreachable_database(client):
    with mock.patch("core.views.connection.cursor", side_effect=OperationalError("down")):
        response = client.get(reverse("core:health"))

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
