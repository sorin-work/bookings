from django.core.management.base import BaseCommand

from appointments.services import expire_unconfirmed


class Command(BaseCommand):
    help = "Mark bookings that weren't confirmed in time as expired."

    def handle(self, *args, **options):
        count = expire_unconfirmed()
        self.stdout.write(f"Expired {count} unconfirmed booking{'s' if count != 1 else ''}.")
