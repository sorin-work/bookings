from functools import cached_property
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .timezones import validate_timezone


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
