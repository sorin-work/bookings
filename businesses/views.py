from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import business_required
from .forms import BusinessForm, BusinessSetupForm, ServiceForm, StaffForm
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


@business_required
def service_list(request):
    services = request.business.services.all()
    context = {
        "services": [s for s in services if s.is_active],
        "archived": [s for s in services if not s.is_active],
    }
    return render(request, "businesses/service_list.html", context)


@business_required
def service_form(request, pk=None):
    business = request.business
    service = get_object_or_404(business.services, pk=pk) if pk else None
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.business = business
        service.save()
        messages.success(request, f"Saved {service.name}.")
        return redirect("businesses:services")
    return render(request, "businesses/service_form.html", {"form": form, "service": service})


@business_required
@require_POST
def service_archive(request, pk):
    service = get_object_or_404(request.business.services, pk=pk)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    if service.is_active:
        messages.success(request, f"{service.name} is bookable again.")
    else:
        messages.success(
            request,
            f"Archived {service.name}. Existing bookings stay, but it can't be booked any more.",
        )
    return redirect("businesses:services")


@business_required
def staff_list(request):
    staff = request.business.staff.prefetch_related("services")
    return render(request, "businesses/staff_list.html", {"staff": staff})


@business_required
def staff_form(request, pk=None):
    business = request.business
    member = get_object_or_404(business.staff, pk=pk) if pk else None
    form = StaffForm(request.POST or None, instance=member, business=business)
    if request.method == "POST" and form.is_valid():
        member = form.save(commit=False)
        member.business = business
        member.save()
        form.save_m2m()
        messages.success(request, f"Saved {member.name}.")
        return redirect("businesses:staff")
    return render(request, "businesses/staff_form.html", {"form": form, "member": member})
