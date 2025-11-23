from django.http import JsonResponse
from django.shortcuts import redirect, render


def health(request):
    return JsonResponse({"status": "ok"})


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "core/landing.html")
