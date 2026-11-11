from typing import Protocol

from django.core.mail import send_mail

from .models import OrderEvent


class NotificationProvider(Protocol):
    def send(self, event: OrderEvent) -> None: ...


class EmailProvider:
    def send(self, event: OrderEvent) -> None:
        order = event.order
        if order.email:
            send_mail(
                "تحديث طلبك من هيام",
                f"طلب {order.pk}\nالحالة: {event.get_status_display()}\n"
                f"الإجمالي: {order.total} ج.م",
                None,
                [order.email],
            )


def get_providers() -> list[NotificationProvider]:
    # Add a WhatsApp provider here; provider must deduplicate using event.pk.
    return [EmailProvider()]
