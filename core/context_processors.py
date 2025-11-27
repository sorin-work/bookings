from businesses.models import Business


def business(request):
    """The signed-in user's business as ``business`` in every template."""
    if hasattr(request, "business"):
        return {"business": request.business}
    user = getattr(request, "user", None)
    return {"business": Business.for_user(user) if user is not None else None}
