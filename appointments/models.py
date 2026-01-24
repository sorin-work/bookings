import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from businesses.models import Business, Service, StaffMember

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_reference():
    """Six characters that are easy to read out on the phone (no 0/O or 1/I)."""
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


class BookingQuerySet(models.QuerySet):
    def blocking(self):
        """Bookings that take up the staff member's time."""
        return self.exclude(status=Booking.Status.CANCELLED)

    def upcoming(self, now=None):
        now = now or timezone.now()
        return self.filter(end__gt=now).exclude(status__in=Booking.CLOSED_STATUSES)


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No-show"

    class CancelledBy(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        BUSINESS = "business", "Business"

    # Statuses that count as a real appointment, in the past or the future.
    ACTIVE_STATUSES = [Status.CONFIRMED, Status.COMPLETED, Status.NO_SHOW]
    CLOSED_STATUSES = [Status.CANCELLED]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=8, unique=True, default=new_reference, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    staff = models.ForeignKey(StaffMember, on_delete=models.PROTECT, related_name="bookings")
    start = models.DateTimeField()
    end = models.DateTimeField()
    # Copied from the service when booking, so later changes to the service don't
    # move existing appointments around.
    buffer_before_minutes = models.PositiveSmallIntegerField(default=0)
    buffer_after_minutes = models.PositiveSmallIntegerField(default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=16, choices=CancelledBy.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return f"{self.reference} {self.customer_name} {self.start:%Y-%m-%d %H:%M}"

    @property
    def busy_start(self):
        return self.start - timedelta(minutes=self.buffer_before_minutes)

    @property
    def busy_end(self):
        return self.end + timedelta(minutes=self.buffer_after_minutes)

    @property
    def local_start(self):
        return self.start.astimezone(self.business.tz)

    @property
    def local_end(self):
        return self.end.astimezone(self.business.tz)

    @property
    def duration_minutes(self):
        return int((self.end - self.start).total_seconds() // 60)

    @property
    def is_open(self):
        """Still going ahead: not cancelled, expired, completed or a no-show."""
        return self.status in (self.Status.CONFIRMED, self.Status.PENDING)

    @property
    def manage_url(self):
        from .tokens import manage_path

        return manage_path(self)
