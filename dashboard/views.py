from django.shortcuts import render

from businesses.decorators import business_required


@business_required
def home(request):
    business = request.business
    return render(request, "dashboard/home.html", {"business": business})
