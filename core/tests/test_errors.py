import pytest
from django.test import Client, override_settings
from django.urls import path

pytestmark = pytest.mark.django_db


def broken(request):
    raise RuntimeError("boom")


urlpatterns = [path("broken/", broken)]


def test_custom_404_page(client):
    response = client.get("/no-such-page/")

    assert response.status_code == 404
    assert "couldn't find that page" in response.content.decode()


@override_settings(ROOT_URLCONF=__name__)
def test_custom_500_page():
    client = Client(raise_request_exception=False)

    response = client.get("/broken/")

    assert response.status_code == 500
    assert "Something went wrong on our side" in response.content.decode()
