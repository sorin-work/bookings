from django.core.management.base import BaseCommand

from notifications.reminders import send_due_reminders


class Command(BaseCommand):
    help = "Email customers whose appointment is in the next 24 hours."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(f"Sent {sent} reminder{'s' if sent != 1 else ''}.")
