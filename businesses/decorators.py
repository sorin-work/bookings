from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Business


def business_required(view):
    """Signed-in views that work on the user's business; sets ``request.business``."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        business = Business.for_user(request.user)
        if business is None:
            return redirect("businesses:setup")
        request.business = business
        return view(request, *args, **kwargs)

    return login_required(wrapper)
