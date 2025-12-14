from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("b/<slug:slug>/", views.business_page, name="business"),
    path("b/<slug:slug>/<int:service_id>/", views.service_page, name="service"),
    path("b/<slug:slug>/<int:service_id>/slots/", views.slots, name="slots"),
    path("b/<slug:slug>/<int:service_id>/book/", views.book, name="book"),
    path("m/<str:token>/", views.manage, name="manage"),
    path("m/<str:token>/cancel/", views.manage_cancel, name="manage_cancel"),
]
