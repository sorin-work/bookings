"""Demo data: a hair salon with four staff and a few months of bookings.

Run with ``python manage.py seed_demo``; the Docker entrypoint does this when
SEED_DEMO=true. Bookings are placed around today, so the calendar and dashboard
always have something to show.
"""

import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from appointments.models import REFERENCE_ALPHABET, Booking
from businesses.models import Business, Service, StaffMember, TimeOff, WorkingHours

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"

SERVICES = [
    # name, minutes, price, buffer before, buffer after, description
    ("Women's cut & finish", 60, "48.00", 0, 10, "Wash, cut and blow-dry."),
    ("Men's cut", 30, "24.00", 0, 5, "Clipper or scissor cut, wash included."),
    ("Blow-dry", 45, "30.00", 0, 5, "Wash and blow-dry, straight or with volume."),
    ("Full head colour", 120, "95.00", 0, 15, "Root to tip colour, includes a toner."),
    ("Balayage", 150, "130.00", 0, 15, "Hand-painted highlights. Book a consultation first."),
    ("Fringe trim", 15, "8.00", 0, 0, "Between cuts."),
    ("Colour consultation", 15, "0.00", 0, 0, "Skin test and a chat about what you'd like."),
]

STAFF = [
    # name, email, colour, services (by index), {weekday: [(start, end), ...]}
    (
        "Amira Hassan",
        "amira@maplestreet.example",
        "#7c3aed",
        [0, 2, 3, 4, 5, 6],
        {1: [(9, 17)], 2: [(9, 17)], 3: [(11, 19)], 4: [(9, 17)], 5: [(9, 15)]},
    ),
    (
        "Tom Becker",
        "tom@maplestreet.example",
        "#0891b2",
        [0, 1, 2, 5],
        {1: [(10, 18)], 2: [(10, 18)], 4: [(10, 14), (15, 19)], 5: [(9, 16)]},
    ),
    (
        "Priya Nair",
        "priya@maplestreet.example",
        "#db2777",
        [0, 2, 3, 4, 5, 6],
        {2: [(9, 17)], 3: [(9, 17)], 4: [(9, 17)], 5: [(9, 15)]},
    ),
    (
        "Jess Walker",
        "",
        "#16a34a",
        [1, 2, 5],
        {1: [(9, 13)], 3: [(13, 19)], 5: [(10, 16)]},
    ),
]

FIRST_NAMES = [
    "Olivia", "Amelia", "Isla", "Ava", "Mia", "Ivy", "Lily", "Isabella", "Rosie", "Sophia",
    "Grace", "Freya", "Ella", "Evie", "Poppy", "Harper", "Sienna", "Chloe", "Maya", "Zara",
    "Noah", "Oliver", "George", "Leo", "Arthur", "Muhammad", "Harry", "Oscar", "Jack", "Theo",
    "Hannah", "Aisha", "Fatima", "Mei", "Sofia", "Elena", "Niamh", "Siobhan", "Kemi", "Ama",
]  # fmt: skip
LAST_NAMES = [
    "Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Patel",
    "Robinson", "Wright", "Thompson", "Evans", "Walker", "White", "Roberts", "Green", "Hall",
    "Khan", "Murphy", "O'Brien", "Kowalski", "Nguyen", "Okafor", "Mensah", "Rossi", "Silva",
]  # fmt: skip
NOTES = [
    "First visit, would like something low maintenance.",
    "Running about 5 minutes late possibly, sorry!",
    "Same as last time please.",
    "Sensitive scalp.",
    "Can we go a bit shorter than usual?",
]


class Command(BaseCommand):
    help = "Create the demo account demo@example.com with a salon and sample bookings."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=2025, help="Random seed for the data.")

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        self.references = set()
        with transaction.atomic():
            business = self._business()
            services = self._services(business)
            staff = self._staff(business, services)
            self._time_off(business, staff)
            count = self._bookings(business, services, staff, rng)
        self.stdout.write(
            self.style.SUCCESS(f"Created {DEMO_EMAIL} / {DEMO_PASSWORD} with {count} bookings.")
        )

    def _business(self):
        user = User.objects.create_user(
            email=DEMO_EMAIL, password=DEMO_PASSWORD, first_name="Dana", last_name="Moreau"
        )
        return Business.objects.create(
            owner=user,
            name="Maple Street Salon",
            slug="maple-street-salon",
            timezone="Europe/London",
            email="hello@maplestreet.example",
            phone="+44 20 7946 0321",
            address="14 Maple Street, London N1 7AB",
            description=(
                "A friendly neighbourhood salon for cuts, colour and blow-dries. "
                "Not sure what to book? Choose a free colour consultation and we'll talk it "
                "through."
            ),
            slot_interval_minutes=15,
            min_notice_minutes=120,
            max_advance_days=60,
        )

    def _services(self, business):
        services = []
        for name, minutes, price, before, after, description in SERVICES:
            services.append(
                Service.objects.create(
                    business=business,
                    name=name,
                    description=description,
                    duration_minutes=minutes,
                    price=Decimal(price),
                    buffer_before_minutes=before,
                    buffer_after_minutes=after,
                )
            )
        return services

    def _staff(self, business, services):
        members = []
        for name, email, _color, service_indexes, hours in STAFF:
            member = StaffMember.objects.create(
                business=business,
                name=name,
                email=email,
            )
            member.services.set([services[i] for i in service_indexes])
            for weekday, shifts in hours.items():
                for start, end in shifts:
                    WorkingHours.objects.create(
                        staff=member, weekday=weekday, start_time=time(start), end_time=time(end)
                    )
            members.append(member)
        return members

    def _time_off(self, business, staff):
        tz = business.tz
        today = business.today()
        holiday = today + timedelta(days=18)
        TimeOff.objects.create(
            staff=staff[2],
            start=datetime.combine(holiday, time(0), tzinfo=tz),
            end=datetime.combine(holiday + timedelta(days=7), time(0), tzinfo=tz),
            reason="Holiday",
        )
        dentist = today + timedelta(days=(3 - today.weekday()) % 7 + 7)
        TimeOff.objects.create(
            staff=staff[1],
            start=datetime.combine(dentist, time(14), tzinfo=tz),
            end=datetime.combine(dentist, time(16), tzinfo=tz),
            reason="Dentist",
        )
        training = today - timedelta(days=40)
        TimeOff.objects.create(
            staff=staff[0],
            start=datetime.combine(training, time(0), tzinfo=tz),
            end=datetime.combine(training + timedelta(days=1), time(0), tzinfo=tz),
            reason="Colour training",
        )

    def _bookings(self, business, services, staff, rng):
        tz = business.tz
        now = timezone.now()
        today = business.today()
        customers = self._customers(rng)
        regulars = customers[:25]
        away = {member.pk: [(t.start, t.end) for t in member.time_off.all()] for member in staff}
        closed = set()
        bookings = []
        for offset in range(-120, 31):
            day = today + timedelta(days=offset)
            if day in closed:
                continue
            midnight = datetime.combine(day, time(0), tzinfo=tz)
            for member in staff:
                offered = list(member.services.all())
                for row in member.working_hours.all():
                    if row.weekday != day.weekday():
                        continue
                    cursor = datetime.combine(day, row.start_time, tzinfo=tz)
                    shift_end = datetime.combine(day, row.end_time, tzinfo=tz)
                    # Further ahead the diary is emptier.
                    fill = 0.8 if offset <= 0 else max(0.15, 0.7 - offset * 0.02)
                    while True:
                        cursor += timedelta(minutes=15 * rng.choice([0, 0, 1, 2, 4]))
                        service = rng.choices(offered, weights=[_weight(s) for s in offered])[0]
                        end = cursor + timedelta(minutes=service.duration_minutes)
                        if end > shift_end:
                            break
                        busy_until = end + timedelta(minutes=service.buffer_after_minutes)
                        is_away = any(s < busy_until and cursor < e for s, e in away[member.pk])
                        if not is_away and rng.random() < fill:
                            customer = rng.choice(regulars if rng.random() < 0.5 else customers)
                            bookings.append(
                                self._booking(business, service, member, cursor, customer, now, rng)
                            )
                        # Carry on from the next quarter hour, like the booking page does.
                        minutes = int((busy_until - midnight).total_seconds() // 60)
                        cursor = midnight + timedelta(minutes=-(-minutes // 15) * 15)
        created = [booking.created_at for booking in bookings]
        Booking.objects.bulk_create(bookings, batch_size=500)
        # bulk_create fills in auto_now_add fields with the current time; put back
        # believable creation times.
        for booking, created_at in zip(bookings, created, strict=True):
            booking.created_at = created_at
        Booking.objects.bulk_update(bookings, ["created_at"], batch_size=500)
        return len(bookings)

    def _booking(self, business, service, member, start, customer, now, rng):
        name, email, phone = customer
        end = start + timedelta(minutes=service.duration_minutes)
        status = Booking.Status.CONFIRMED
        cancelled_at = None
        cancelled_by = ""
        roll = rng.random()
        if roll < 0.07:
            status = Booking.Status.CANCELLED
            cancelled_at = min(now, start - timedelta(hours=rng.randint(2, 72)))
            cancelled_by = rng.choice(
                [Booking.CancelledBy.CUSTOMER] * 4 + [Booking.CancelledBy.BUSINESS]
            )
        elif end <= now:
            status = Booking.Status.NO_SHOW if roll < 0.10 else Booking.Status.COMPLETED
        # Booked one to three weeks ahead, at a waking hour.
        created = (start - timedelta(days=rng.randint(1, 21))).replace(
            hour=rng.randint(7, 22), minute=rng.randint(0, 59)
        )
        booking = Booking(
            reference=self._reference(rng),
            business=business,
            service=service,
            staff=member,
            start=start,
            end=end,
            buffer_before_minutes=service.buffer_before_minutes,
            buffer_after_minutes=service.buffer_after_minutes,
            price=service.price,
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
            status=status,
            cancelled_at=cancelled_at,
            cancelled_by=cancelled_by,
        )
        booking.created_at = min(created, now)
        return booking

    def _reference(self, rng):
        """Booking references from the seeded generator, so they can't collide."""
        while True:
            reference = "".join(rng.choice(REFERENCE_ALPHABET) for _ in range(6))
            if reference not in self.references:
                self.references.add(reference)
                return reference

    def _customers(self, rng):
        people = []
        used = set()
        while len(people) < 90:
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            if (first, last) in used:
                continue
            used.add((first, last))
            handle = f"{first}.{last}".lower().replace("'", "")
            domain = rng.choice(["example.com", "example.org", "example.net"])
            phone = f"+44 7700 9{rng.randint(0, 99999):05d}"
            people.append((f"{first} {last}", f"{handle}@{domain}", phone))
        return people


def _weight(service):
    """How often each service gets booked: cuts a lot, consultations rarely."""
    return {15: 2, 30: 6, 45: 4, 60: 8, 120: 3, 150: 1}.get(service.duration_minutes, 2)
