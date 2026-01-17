from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "start", "customer_name", "service", "staff", "status"]
    list_filter = ["status", "business"]
    search_fields = ["reference", "customer_name", "customer_email", "customer_phone"]
    date_hierarchy = "start"
    raw_id_fields = ["service", "staff"]
    readonly_fields = ["public_id", "reference", "created_at", "updated_at"]
