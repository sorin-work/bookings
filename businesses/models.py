from datetime import time
from functools import cached_property
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .timezones import validate_timezone

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class Business(models.Model):
    """A salon, practice or tutor: owns the services, staff and bookings."""

    SLOT_INTERVAL_CHOICES = [
        (5, "5 minutes"),
        (10, "10 minutes"),
        (15, "15 minutes"),
        (20, "20 minutes"),
        (30, "30 minutes"),
        (60, "1 hour"),
    ]

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=60,
        unique=True,
        help_text="Used in the address of your booking page.",
    )
    timezone = models.CharField(
        max_length=64, default="Europe/London", validators=[validate_timezone]
    )
    email = models.EmailField(
        blank=True, help_text="Booking notifications go here. Leave empty to use your login email."
    )
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text="Shown at the top of your booking page.")
    slot_interval_minutes = models.PositiveSmallIntegerField(
        default=15,
        choices=SLOT_INTERVAL_CHOICES,
        help_text="How far apart the start times offered to customers are.",
    )
    min_notice_minutes = models.PositiveIntegerField(
        default=120, help_text="Customers can't book closer to the start than this."
    )
    max_advance_days = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="How many days ahead customers can book.",
    )
    require_confirmation = models.BooleanField(
        default=False,
        help_text="Customers confirm their booking from a link in the email before it counts.",
    )
    cancellation_notice_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text="Customers can cancel or move a booking up to this many hours before it starts.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "businesses"

    def __str__(self):
        return self.name

    @classmethod
    def for_user(cls, user):
        if not user.is_authenticated:
            return None
        try:
            return user.business
        except cls.DoesNotExist:
            return None

    @cached_property
    def tz(self):
        return ZoneInfo(self.timezone)

    @property
    def notification_email(self):
        return self.email or self.owner.email

    def local_now(self):
        return timezone.now().astimezone(self.tz)

    def today(self):
        return self.local_now().date()


class Service(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        "duration (minutes)", validators=[MinValueValidator(5), MaxValueValidator(12 * 60)]
    )
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    buffer_before_minutes = models.PositiveSmallIntegerField(
        "buffer before (minutes)",
        default=0,
        validators=[MaxValueValidator(240)],
        help_text="Time kept free before the appointment, for example to set up.",
    )
    buffer_after_minutes = models.PositiveSmallIntegerField(
        "buffer after (minutes)",
        default=0,
        validators=[MaxValueValidator(240)],
        help_text="Time kept free afterwards, for example to clean up.",
    )
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class StaffMember(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="staff")
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    services = models.ManyToManyField(Service, related_name="staff", blank=True)
    color = models.CharField(
        max_length=7,
        default="#2563eb",
        validators=[RegexValidator(HEX_COLOR, "Use a colour like #2563eb.")],
    )
    is_active = models.BooleanField(
        default=True, help_text="Inactive staff keep their history but can't be booked."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "staff member"

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    """One stretch of work on a weekday. Several rows on a day make a split shift."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6

    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField(default=time(9))
    end_time = models.TimeField(default=time(17))

    class Meta:
        ordering = ["weekday", "start_time"]
        verbose_name_plural = "working hours"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="working_hours_end_after_start"
            )
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class TimeOff(models.Model):
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="time_off")
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["start"]
        verbose_name_plural = "time off"

    def __str__(self):
        return f"{self.staff}: {self.start:%Y-%m-%d %H:%M} – {self.end:%Y-%m-%d %H:%M}"


class ClosedDay(models.Model):
    """A day the whole business is shut, like a bank holiday."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="closed_days")
    date = models.DateField()
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["business", "date"], name="closed_day_unique_date")
        ]

    def __str__(self):
        return f"{self.business}: closed {self.date:%Y-%m-%d}"
