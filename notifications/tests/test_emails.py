import pytest
from django.core import mail

from appointments import services
from appointments.models import Booking
from testutils import at, next_weekday

pytestmark = pytest.mark.django_db


@pytest.fixture
def send(django_capture_on_commit_callbacks):
    """Run a booking action and return the emails it sent."""

    def run(func, *args, **kwargs):
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            result = func(*args, **kwargs)
        return result, list(mail.outbox)

    return run


def customer(name="Ana Lima"):
    return services.Customer(name=name, email="ana@example.com", phone="07700900123")


def test_new_booking_emails_the_customer_and_the_business(send, service, staff):
    booking, sent = send(
        services.create_booking, service, at(next_weekday(0), 10), customer(), staff
    )

    to_customer = next(m for m in sent if m.to == ["ana@example.com"])
    to_business = next(m for m in sent if "owner@example.com" in m.to)
    assert to_customer.subject.startswith("Booking confirmed: Haircut on ")
    assert "10:00" in to_customer.subject
    assert booking.reference in to_customer.body
    assert "/m/" in to_customer.body  # the booking link
    assert to_business.subject.startswith("New booking: Ana Lima, Haircut")
    assert to_business.reply_to == ["ana@example.com"]


def test_times_in_emails_are_in_the_business_s_time_zone(send, business, service, staff):
    business.timezone = "America/New_York"
    business.save()
    service.refresh_from_db()
    start = at(next_weekday(0), 10, tz=business.tz)

    _, sent = send(services.create_booking, service, start, customer(), staff)

    assert "10:00" in sent[0].body


def test_cancelling_emails_both_sides(send, service, staff):
    booking = services.create_booking(service, at(next_weekday(0), 10), customer(), staff)

    _, sent = send(services.cancel_booking, booking, Booking.CancelledBy.CUSTOMER)

    subjects = sorted(m.subject.split(":")[0] for m in sent)
    assert subjects == ["Booking cancelled", "Cancelled"]


def test_business_cancelling_only_emails_the_customer(send, service, staff):
    booking = services.create_booking(service, at(next_weekday(0), 10), customer(), staff)

    _, sent = send(services.cancel_booking, booking, Booking.CancelledBy.BUSINESS)

    assert [m.to for m in sent] == [["ana@example.com"]]
    assert "had to cancel" in sent[0].body


def test_moving_emails_the_new_and_old_time(send, service, staff):
    booking = services.create_booking(service, at(next_weekday(0), 10), customer(), staff)

    _, sent = send(services.reschedule_booking, booking, at(next_weekday(0), 14))

    to_customer = next(m for m in sent if m.to == ["ana@example.com"])
    assert "14:00" in to_customer.subject
    assert "10:00" in to_customer.body
