from decimal import Decimal
from io import BytesIO
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from PIL import Image

from store.forms import CheckoutForm
from store.models import Notification, Order, ProductImage, Variant
from store.services import CheckoutError, checkout, transition_order
from store.tasks import deliver_notifications
from store.uploads import prepare_image

from .conftest import ProductFactory, VariantFactory

pytestmark = pytest.mark.django_db
DETAILS = {
    "name": "منى",
    "phone": "+201012345678",
    "email": "mona@example.com",
    "address": "القاهرة، مدينة نصر، شارع ١، عمارة ٢",
}


def place(
    variant: Variant, quantity: int = 2, key: Any = None, session: str | None = None
) -> Order:
    if session is None:
        client = Client()
        session = client.session.session_key
    assert session
    return checkout(
        cart={str(variant.pk): quantity},
        session_key=session,
        key=key or uuid4(),
        details=DETAILS,
    )


def test_decimal_checkout_and_snapshot(variant: Variant) -> None:
    order = place(variant)
    assert order.total == Decimal("251.10")
    assert order.currency == "EGP"
    variant.refresh_from_db()
    assert variant.stock == 8
    variant.price = Decimal("999.99")
    variant.save()
    assert order.lines.get().unit_price == Decimal("125.55")
    assert order.events.count() == 1
    assert Notification.objects.count() == 1


def test_retry_is_idempotent_and_session_bound(variant: Variant) -> None:
    key = uuid4()
    session = Client().session.session_key
    first = place(variant, key=key, session=session)
    assert place(variant, key=key, session=session).pk == first.pk
    with pytest.raises(CheckoutError):
        place(variant, key=key)
    variant.refresh_from_db()
    assert variant.stock == 8


@pytest.mark.parametrize("quantity", [0, -1, 11, True, "2"])
def test_invalid_quantities(variant: Variant, quantity: Any) -> None:
    with pytest.raises(CheckoutError):
        place(variant, quantity)
    assert not Order.objects.exists()


def test_invalid_or_empty_cart(variant: Variant) -> None:
    session = Client().session.session_key
    assert session
    for cart in ({}, {"invalid": 2}, {"999999": 1}, {str(i): 1 for i in range(51)}):
        with pytest.raises(CheckoutError):
            checkout(cart=cart, session_key=session, key=uuid4(), details=DETAILS)


def test_insufficient_stock_rolls_back_entire_order(variant: Variant) -> None:
    other = cast(Variant, VariantFactory(stock=0))
    session = Client().session.session_key
    assert session
    with pytest.raises(CheckoutError):
        checkout(
            cart={str(variant.pk): 1, str(other.pk): 1},
            session_key=session,
            key=uuid4(),
            details=DETAILS,
        )
    variant.refresh_from_db()
    assert variant.stock == 10
    assert not Order.objects.exists()


def test_inactive_product_cannot_be_ordered(variant: Variant) -> None:
    variant.product.active = False
    variant.product.save()
    with pytest.raises(CheckoutError):
        place(variant)


@pytest.mark.parametrize(
    "path",
    [
        ["paid", "shipped", "delivered", "returned"],
        ["cancelled"],
        ["shipped", "returned"],
    ],
)
def test_status_flow_restores_stock_once(variant: Variant, path: list[str]) -> None:
    order = place(variant)
    for target in path:
        transition_order(order.pk, target)
        transition_order(order.pk, target)
    variant.refresh_from_db()
    assert variant.stock == 10
    assert order.events.count() == len(path) + 1
    with pytest.raises(CheckoutError):
        transition_order(order.pk, "paid")


def test_invalid_transition_changes_nothing(variant: Variant) -> None:
    order = place(variant)
    with pytest.raises(CheckoutError):
        transition_order(order.pk, "delivered")
    order.refresh_from_db()
    assert order.status == "pending"


def test_database_price_constraint(variant: Variant) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Variant.objects.filter(pk=variant.pk).update(price=0)


@pytest.mark.parametrize(
    "phone", ["01012345678", "+201012345678", "٠١٠١٢٣٤٥٦٧٨", "010 1234 5678"]
)
def test_phone_normalization(phone: str) -> None:
    form = CheckoutForm({**DETAILS, "phone": phone, "key": uuid4()})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["phone"] == "+201012345678"


def test_invalid_phone() -> None:
    form = CheckoutForm({**DETAILS, "phone": "0123", "key": uuid4()})
    assert not form.is_valid()


def test_catalog_detail_and_api(client: Client, variant: Variant) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'dir="rtl"' in response.content.decode()
    assert variant.product.name in response.content.decode()
    assert "Content-Security-Policy" in response
    detail = client.get(reverse("product", args=[variant.product.slug]))
    assert detail.status_code == 200
    assert '"priceCurrency": "EGP"' in detail.content.decode()
    assert (
        client.get("/api/products/").json()["results"][0]["variants"][0]["price"]
        == "125.55"
    )
    assert client.post("/api/products/", {}).status_code in {403, 405}
    assert str(variant) and str(variant.product) and str(variant.product.category)


def test_filters_htmx_and_invalid_prices(client: Client, variant: Variant) -> None:
    params = {
        "q": "عباية",
        "category": variant.product.category.slug,
        "size": "XL",
        "color": "أسود",
        "min_price": "100",
        "max_price": "200",
    }
    response = client.get("/", params, HTTP_HX_REQUEST="true")
    assert variant.product.name in response.content.decode()
    assert "<html" not in response.content.decode()
    assert (
        variant.product.name not in client.get("/", {"size": "XXXS"}).content.decode()
    )
    for amount in ("NaN", "Infinity", "-1", "oops", "1e1000"):
        assert client.get("/", {"min_price": amount}).status_code == 400


def test_filters_must_match_same_variant(client: Client, variant: Variant) -> None:
    VariantFactory(product=variant.product, size="S", color="أبيض")
    assert (
        variant.product.name
        not in client.get("/", {"size": "S", "color": "أسود"}).content.decode()
    )


def test_query_budget(
    client: Client, django_assert_num_queries: Any, variant: Variant
) -> None:
    for _ in range(12):
        VariantFactory()
    with django_assert_num_queries(5):
        assert client.get("/").status_code == 200
    with django_assert_num_queries(1):
        assert client.get("/").status_code == 200
    with django_assert_num_queries(3):
        assert (
            client.get(reverse("product", args=[variant.product.slug])).status_code
            == 200
        )


def test_cart_checkout_and_order_privacy(client: Client, variant: Variant) -> None:
    assert client.get("/cart/").status_code == 200
    assert (
        client.post("/cart/update/", {"variant": variant.pk, "quantity": 2}).status_code
        == 302
    )
    assert "251.10" in client.get("/cart/").content.decode()
    page = client.get("/checkout/")
    key = page.context["form"].initial["key"]
    response = client.post("/checkout/", {**DETAILS, "key": key})
    assert response.status_code == 302
    url = response["Location"]
    assert client.get(url).status_code == 200
    assert Client().get(url).status_code == 404
    assert client.post("/checkout/", {**DETAILS, "key": key}).status_code == 302
    assert Order.objects.count() == 1
    assert not client.session["cart"]


def test_cart_validation_and_removal(client: Client, variant: Variant) -> None:
    assert client.get("/cart/update/").status_code == 405
    assert (
        client.post(
            "/cart/update/", {"variant": variant.pk, "quantity": 11}
        ).status_code
        == 400
    )
    variant.stock = 1
    variant.save()
    assert (
        client.post("/cart/update/", {"variant": variant.pk, "quantity": 2}).status_code
        == 400
    )
    client.post("/cart/update/", {"variant": variant.pk, "quantity": 1})
    client.post("/cart/update/", {"variant": variant.pk, "quantity": 0})
    assert not client.session["cart"]
    assert (
        client.post("/cart/update/", {"variant": 999999, "quantity": 1}).status_code
        == 404
    )


def test_checkout_errors_and_stale_key(client: Client, variant: Variant) -> None:
    page = client.get("/checkout/")
    key = page.context["form"].initial["key"]
    assert client.post("/checkout/", {**DETAILS, "key": key}).status_code == 400
    assert client.post("/checkout/", {**DETAILS, "key": uuid4()}).status_code == 400
    assert client.post("/checkout/", {}).status_code == 400


def test_csrf_enforced(variant: Variant) -> None:
    assert (
        Client(enforce_csrf_checks=True)
        .post("/cart/update/", {"variant": variant.pk, "quantity": 1})
        .status_code
        == 403
    )


def test_image_reencoding_and_thumbnail(
    variant: Variant, settings: Any, tmp_path: Any
) -> None:
    settings.MEDIA_ROOT = tmp_path
    stream = BytesIO()
    Image.new("RGB", (1800, 1200), "red").save(stream, "PNG")
    image = ProductImage.objects.create(
        product=variant.product,
        image=SimpleUploadedFile("test.png", stream.getvalue(), "image/png"),
        alt="عباية حمراء",
    )
    with Image.open(image.image) as picture:
        assert picture.format == "WEBP"
        assert max(picture.size) <= 1600
    with Image.open(image.thumbnail) as thumbnail:
        assert max(thumbnail.size) <= 400
    client = Client()
    assert image.thumbnail.url in client.get("/").content.decode()
    assert (
        image.image.url
        in client.get(reverse("product", args=[variant.product.slug])).content.decode()
    )


@pytest.mark.parametrize(
    "content",
    [b"<svg><script>bad</script></svg>", b"bad", b"x" * (5 * 1024 * 1024 + 1)],
)
def test_invalid_upload(content: bytes) -> None:
    with pytest.raises(ValidationError):
        prepare_image(SimpleUploadedFile("bad.jpg", content, "image/jpeg"))  # type: ignore[arg-type]


def test_gif_rejected() -> None:
    stream = BytesIO()
    Image.new("RGB", (2, 2)).save(stream, "GIF")
    with pytest.raises(ValidationError):
        prepare_image(SimpleUploadedFile("bad.gif", stream.getvalue()))  # type: ignore[arg-type]


def test_notifications_retry_and_no_duplicate(variant: Variant) -> None:
    place(variant)
    with patch("store.notifications.send_mail", side_effect=OSError("offline")):
        assert deliver_notifications() == 0
    assert Notification.objects.get().sent_at is None
    assert Notification.objects.get().attempts == 1
    assert deliver_notifications() == 1
    assert len(mail.outbox) == 1
    assert deliver_notifications() == 0


def test_notification_without_email(variant: Variant) -> None:
    order = place(variant)
    order.email = ""
    order.save()
    assert deliver_notifications() == 1
    assert not mail.outbox


def test_health_seo_and_errors(client: Client, variant: Variant) -> None:
    assert client.get("/health/").json() == {"status": "ok"}
    with patch("store.views.cache.get", return_value=False):
        assert client.get("/health/").status_code == 503
    assert "Sitemap:" in client.get("/robots.txt").content.decode()
    assert variant.product.slug in client.get("/sitemap.xml").content.decode()
    assert client.get("/missing/").status_code == 404


def test_admin_permissions_and_transitions(client: Client, variant: Variant) -> None:
    order = place(variant)
    assert client.get("/admin/store/order/").status_code == 302
    user = User.objects.create_user("customer", password="test-password")
    client.force_login(user)
    assert client.get("/admin/store/order/").status_code == 302
    user.is_staff = True
    user.save()
    assert client.get("/admin/store/order/").status_code == 403
    user.user_permissions.add(
        *Permission.objects.filter(codename__in=["view_order", "change_order"])
    )
    assert client.get("/admin/store/order/").status_code == 200
    assert (
        client.post(
            "/admin/store/order/",
            {"action": "mark_shipped", "_selected_action": str(order.pk)},
        ).status_code
        == 302
    )
    order.refresh_from_db()
    assert order.status == "shipped"
    assert "Content-Security-Policy" not in client.get("/admin/")
    assert Session.objects.exists()


def test_pagination(client: Client, variant: Variant) -> None:
    for _ in range(13):
        ProductFactory()
    page = client.get("/")
    assert page.context["page"].paginator.count == 14
    assert client.get("/", {"page": "2"}).context["page"].number == 2


def test_jsonld_xss_escape(client: Client, variant: Variant) -> None:
    variant.product.name = "</script><script>alert(1)</script>"
    variant.product.save()
    response = client.get(reverse("product", args=[variant.product.slug]))
    assert "\\u003c/script>" in response.content.decode()
    assert "<script>alert(1)</script>" not in response.content.decode()
