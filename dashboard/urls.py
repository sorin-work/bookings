from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", views.home, name="home"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("bookings/<int:pk>/", views.booking_detail, name="booking"),
    path("bookings/<int:pk>/outcome/", views.booking_outcome, name="booking_outcome"),
]
