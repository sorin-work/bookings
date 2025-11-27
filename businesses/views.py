from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .decorators import business_required
from .forms import BusinessForm, BusinessSetupForm
from .models import Business
from .utils import unique_slug


@login_required
def setup(request):
    """For accounts without a business yet, like ones made with createsuperuser."""
    if Business.for_user(request.user):
        return redirect("businesses:settings")
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and not data.get("slug"):
        data["slug"] = unique_slug(data.get("name", ""))
    form = BusinessSetupForm(data, initial={"email": request.user.email})
    form.fields["slug"].required = False
    if request.method == "POST" and form.is_valid():
        business = form.save(commit=False)
        business.owner = request.user
        business.save()
        messages.success(request, "Your business is set up.")
        return redirect("dashboard:home")
    return render(request, "businesses/setup.html", {"form": form})


@business_required
def settings_view(request):
    business = request.business
    form = BusinessForm(request.POST or None, instance=business)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("businesses:settings")
    return render(request, "businesses/settings.html", {"form": form})
