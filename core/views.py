import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


def health(request):
    """Liveness and readiness in one: the app is only useful with its database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Health check could not reach the database")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "core/landing.html")
