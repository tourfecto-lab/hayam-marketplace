import logging

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Notification
from .notifications import get_providers

logger = logging.getLogger(__name__)


@shared_task
def deliver_notifications() -> int:
    delivered = 0
    pending = list(
        Notification.objects.filter(sent_at__isnull=True)
        .order_by("pk")
        .values_list("pk", flat=True)[:100]
    )
    for pk in pending:
        Notification.objects.filter(pk=pk, sent_at__isnull=True).update(
            attempts=F("attempts") + 1
        )
        try:
            with transaction.atomic():
                notification = (
                    Notification.objects.select_for_update()
                    .select_related("event__order")
                    .get(pk=pk)
                )
                if notification.sent_at:
                    continue
                for provider in get_providers():
                    provider.send(notification.event)
                notification.sent_at = timezone.now()
                notification.save(update_fields=["sent_at"])
                delivered += 1
        except Exception:
            # No customer data or provider response bodies enter logs.
            logger.warning("Notification %s delivery failed; queued for retry", pk)
    return delivered
