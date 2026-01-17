from django.contrib import admin

from .models import Business, Service, StaffMember, TimeOff, WorkingHours


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ["name", "duration_minutes", "price", "is_active"]


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "timezone", "created_at"]
    search_fields = ["name", "slug", "owner__email"]
    inlines = [ServiceInline]


class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 0


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "email"]
    list_filter = ["business"]
    search_fields = ["name", "email"]
    inlines = [WorkingHoursInline]


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ["staff", "start", "end", "reason"]
    list_filter = ["staff__business"]
