import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_htmx_request_without_a_session_redirects_the_whole_page(client):
    response = client.get(reverse("dashboard:calendar"), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert response["HX-Redirect"].startswith(reverse("accounts:login"))


def test_normal_requests_still_get_a_redirect(client):
    response = client.get(reverse("dashboard:calendar"))

    assert response.status_code == 302
