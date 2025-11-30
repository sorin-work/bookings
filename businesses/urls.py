from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/setup/", views.setup, name="setup"),
    path("services/", views.service_list, name="services"),
    path("services/new/", views.service_form, name="service_new"),
    path("services/<int:pk>/edit/", views.service_form, name="service_edit"),
    path("services/<int:pk>/archive/", views.service_archive, name="service_archive"),
    path("staff/", views.staff_list, name="staff"),
    path("staff/new/", views.staff_form, name="staff_new"),
    path("staff/<int:pk>/edit/", views.staff_form, name="staff_edit"),
    path("staff/<int:pk>/hours/", views.staff_hours, name="staff_hours"),
]
