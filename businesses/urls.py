from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/setup/", views.setup, name="setup"),
    path("services/", views.service_list, name="services"),
    path("services/new/", views.service_form, name="service_new"),
    path("services/<int:pk>/edit/", views.service_form, name="service_edit"),
]
