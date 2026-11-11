from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import F

from .models import Notification, Order, OrderEvent, OrderLine, Variant
from .signals import invalidate_catalog


class CheckoutError(ValueError):
    pass


def record_event(order: Order) -> None:
    event = OrderEvent.objects.create(order=order, status=order.status)
    Notification.objects.create(event=event)


@transaction.atomic
def checkout(
    *, cart: Mapping[str, int], session_key: str, key: UUID, details: dict[str, Any]
) -> Order:
    # Serialize retries for the same session as well as locking stock rows below.
    from django.contrib.sessions.models import Session

    if not Session.objects.select_for_update().filter(session_key=session_key).exists():
        raise CheckoutError("الجلسة انتهت. افتحي المتجر تاني وحاولي.")
    previous = Order.objects.filter(checkout_key=key).first()
    if previous:
        if previous.session_key != session_key:
            raise CheckoutError("تعذر تأكيد الطلب. حاول تاني.")
        return previous
    if not cart or len(cart) > 50:
        raise CheckoutError("السلة فاضية أو فيها منتجات كتير.")
    try:
        quantities = {int(k): v for k, v in cart.items()}
    except (ValueError, TypeError) as exc:
        raise CheckoutError("السلة غير صالحة.") from exc
    if any(type(v) is not int or not 1 <= v <= 10 for v in quantities.values()):
        raise CheckoutError("الكمية لازم تكون من ١ لـ ١٠.")
    variants = list(
        Variant.objects.select_for_update()
        .select_related("product")
        .filter(pk__in=quantities)
        .order_by("pk")
    )
    if len(variants) != len(quantities):
        raise CheckoutError("منتج مش متاح دلوقتي.")
    total = Decimal("0.00")
    for variant in variants:
        if not variant.product.active or variant.stock < quantities[variant.pk]:
            raise CheckoutError("للأسف الكمية المطلوبة مش متاحة.")
        total += variant.price * quantities[variant.pk]
    if total > Decimal("9999999999.99"):
        raise CheckoutError("قيمة الطلب أكبر من الحد المسموح.")
    order = Order.objects.create(
        checkout_key=key, session_key=session_key, total=total, **details
    )
    for variant in variants:
        count = quantities[variant.pk]
        # Conditional update protects backends that lack row locks as well.
        changed = Variant.objects.filter(pk=variant.pk, stock__gte=count).update(
            stock=F("stock") - count
        )
        if changed != 1:
            raise CheckoutError("للأسف الكمية المطلوبة مش متاحة.")
        OrderLine.objects.create(
            order=order,
            variant=variant,
            quantity=count,
            unit_price=variant.price,
            product_name=variant.product.name,
            options=f"{variant.size} / {variant.color}",
        )
    record_event(order)
    invalidate_catalog()
    return order


TRANSITIONS: dict[str, set[str]] = {
    Order.Status.PENDING: {
        Order.Status.PAID,
        Order.Status.SHIPPED,
        Order.Status.CANCELLED,
    },
    Order.Status.PAID: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED, Order.Status.RETURNED},
    Order.Status.DELIVERED: {Order.Status.RETURNED},
    Order.Status.CANCELLED: set(),
    Order.Status.RETURNED: set(),
}


@transaction.atomic
def transition_order(order_id: UUID, target: str) -> Order:
    order = Order.objects.select_for_update().get(pk=order_id)
    if target == order.status:
        return order
    if target not in TRANSITIONS[order.status]:
        raise CheckoutError("Invalid order status transition.")
    if target in {Order.Status.CANCELLED, Order.Status.RETURNED}:
        for line in order.lines.order_by("variant_id"):
            Variant.objects.filter(pk=line.variant_id).update(
                stock=F("stock") + line.quantity
            )
    order.status = target
    order.save(update_fields=["status"])
    record_event(order)
    invalidate_catalog()
    return order
