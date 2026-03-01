from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.utils import timezone

from businesses.models import Business


class BusinessTimezoneMiddleware:
    """Show times in the signed-in business's time zone.

    Public booking pages activate the zone of the business they belong to, so
    the zone is reset after every request to not leak into the next one.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        business = Business.for_user(request.user)
        if business is not None:
            timezone.activate(business.tz)
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()


class HtmxLoginRedirectMiddleware:
    """When the session ran out, htmx would swap the login page into a panel.

    Answer htmx requests that get redirected to the login page with HX-Redirect,
    so the whole page goes there instead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get("HX-Request") and response.status_code == 302:
            login_url = resolve_url(settings.LOGIN_URL)
            if response["Location"].startswith(login_url):
                redirect = HttpResponse(status=204)
                redirect["HX-Redirect"] = response["Location"]
                return redirect
        return response
