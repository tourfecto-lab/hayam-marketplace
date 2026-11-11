from typing import Any

from django.core.management.base import BaseCommand

from store.tasks import deliver_notifications


class Command(BaseCommand):
    help = "Deliver pending notifications synchronously (local development)."

    def handle(self, *args: Any, **options: Any) -> None:
        count = deliver_notifications()
        self.stdout.write(f"Delivered {count} notification(s).")
