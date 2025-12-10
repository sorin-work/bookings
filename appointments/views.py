"""Public pages: the booking page of each business and the customer's booking link."""

from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from businesses.models import Business
from scheduling import availability


def _business(slug):
    business = get_object_or_404(Business, slug=slug)
    # Customers see times in the business's time zone, wherever they are.
    timezone.activate(business.tz)
    return business


def _public_services(business):
    services_qs = business.services.filter(is_active=True)
    return services_qs


def business_page(request, slug):
    business = _business(slug)
    offered = [s for s in _public_services(business) if availability.bookable_staff(s).exists()]
    context = {"business": business, "services": offered}
    return render(request, "appointments/business.html", context)
