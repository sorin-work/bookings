from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("b/<slug:slug>/", views.business_page, name="business"),
]
