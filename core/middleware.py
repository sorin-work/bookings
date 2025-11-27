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
