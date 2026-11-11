from io import StringIO
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

from store.models import Product, Variant
from store.services import CheckoutError, checkout, transition_order
from store.tasks import deliver_notifications

from .test_store import place

pytestmark = pytest.mark.django_db


def test_rate_limit_and_trusted_proxy(client: Client, settings: Any) -> None:
    for _ in range(20):
        assert client.post("/checkout/", {}).status_code == 400
    response = client.post("/checkout/", {})
    assert response.status_code == 429
    assert response["Retry-After"] == "300"
    settings.TRUST_PROXY = True
    assert (
        client.post("/checkout/", {}, HTTP_X_FORWARDED_FOR="192.0.2.1").status_code
        == 400
    )


def test_cache_invalidation_after_checkout(
    client: Client, variant: Variant, django_capture_on_commit_callbacks: Any
) -> None:
    client.get("/")
    before = cache.get("catalog-version")
    with django_capture_on_commit_callbacks(execute=True):
        place(variant)
    assert cache.get("catalog-version") != before


def test_admin_all_status_actions(client: Client, variant: Variant) -> None:
    user = User.objects.create_superuser("admin", "admin@example.com", "test-password")
    client.force_login(user)
    order = place(variant)
    url = f"/admin/store/order/{order.pk}/change/"
    assert client.get(url).status_code == 200
    for action in (
        "mark_paid",
        "mark_delivered",
        "mark_shipped",
        "mark_delivered",
        "mark_returned",
    ):
        assert (
            client.post(
                "/admin/store/order/",
                {"action": action, "_selected_action": str(order.pk)},
            ).status_code
            == 302
        )
    order.refresh_from_db()
    assert order.status == "returned"
    second = place(variant)
    client.post(
        "/admin/store/order/",
        {"action": "mark_cancelled", "_selected_action": str(second.pk)},
    )
    second.refresh_from_db()
    assert second.status == "cancelled"
    assert client.get("/admin/store/product/add/").status_code == 200
    assert client.get("/admin/store/notification/").status_code == 200


def test_commands_repeatable(variant: Variant) -> None:
    output = StringIO()
    call_command("seed_demo", stdout=output)
    total = Product.objects.count()
    call_command("seed_demo", stdout=output)
    assert Product.objects.count() == total
    place(variant)
    call_command("deliver_notifications", stdout=output)
    assert "Delivered 1" in output.getvalue()


def test_friendly_500(client: Client) -> None:
    client.raise_request_exception = False
    with patch("store.views.catalog_products", side_effect=RuntimeError("broken")):
        response = client.get("/")
    assert response.status_code == 500
    assert "حصلت مشكلة بسيطة" in response.content.decode()


def test_cancelled_terminal(variant: Variant) -> None:
    order = place(variant)
    transition_order(order.pk, "cancelled")
    assert order.lines.count() == 1


def test_inactive_cart_item_can_be_removed(client: Client, variant: Variant) -> None:
    client.post("/cart/update/", {"variant": variant.pk, "quantity": 1})
    variant.product.active = False
    variant.product.save()
    assert variant.product.name in client.get("/cart/").content.decode()
    assert (
        client.post("/cart/update/", {"variant": variant.pk, "quantity": 1}).status_code
        == 400
    )
    assert (
        client.post("/cart/update/", {"variant": variant.pk, "quantity": 0}).status_code
        == 302
    )
    assert not client.session["cart"]


def test_missing_session_rejected(variant: Variant) -> None:
    from uuid import uuid4

    with pytest.raises(CheckoutError):
        checkout(
            cart={str(variant.pk): 1}, session_key="missing", key=uuid4(), details={}
        )


def test_total_limit_rejected(variant: Variant) -> None:
    from decimal import Decimal

    variant.price = Decimal("9999999999.99")
    variant.save()
    with pytest.raises(CheckoutError):
        place(variant, quantity=2)


def test_failed_notification_does_not_block_others(variant: Variant) -> None:
    from store.models import Notification

    place(variant)
    place(variant)
    with patch("store.notifications.send_mail", side_effect=[OSError("offline"), 1]):
        assert deliver_notifications() == 1
    assert Notification.objects.filter(sent_at__isnull=True).count() == 1
