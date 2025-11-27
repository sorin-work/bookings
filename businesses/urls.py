from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path("settings/setup/", views.setup, name="setup"),
]
