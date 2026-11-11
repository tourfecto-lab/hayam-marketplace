import json
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Prefetch, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import CartForm, CheckoutForm
from .models import Category, Order, Product, Variant
from .services import CheckoutError, checkout


def catalog_products() -> Any:
    return (
        Product.objects.filter(active=True)
        .select_related("category")
        .prefetch_related(
            Prefetch("variants", queryset=Variant.objects.order_by("price", "pk")),
            "images",
        )
        .order_by("pk")
    )


@require_GET
def catalog(request: HttpRequest) -> HttpResponse:
    products = catalog_products()
    query = request.GET.get("q", "")[:100]
    category = request.GET.get("category", "")[:100]
    size = request.GET.get("size", "")[:30]
    color = request.GET.get("color", "")[:50]
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
    if category:
        products = products.filter(category__slug=category)
    variants: dict[str, Any] = {}
    if size:
        variants["size"] = size
    if color:
        variants["color"] = color
    for field in ("min_price", "max_price"):
        value = request.GET.get(field, "")
        if value:
            try:
                amount = Decimal(value)
                if not amount.is_finite() or not 0 <= amount <= Decimal(
                    "9999999999.99"
                ):
                    raise InvalidOperation
            except InvalidOperation:
                return render(
                    request,
                    "store/catalog.html",
                    {
                        "filter_error": "اكتب سعر صحيح.",
                        "categories": Category.objects.all(),
                    },
                    status=400,
                )
            variants["price__gte" if field == "min_price" else "price__lte"] = amount
    if variants:
        products = products.filter(
            variants__in=Variant.objects.filter(**variants)
        ).distinct()
    # Cache product objects only, never rendered HTML containing session/CSRF data.
    version = cache.get("catalog-version", "initial")
    import hashlib

    filters = json.dumps(
        [
            query,
            category,
            size,
            color,
            request.GET.get("min_price"),
            request.GET.get("max_price"),
            request.GET.get("page", "1"),
        ]
    )
    key = f"catalog:{version}:{hashlib.sha256(filters.encode()).hexdigest()}"
    payload = cache.get(key)
    if payload is None:
        page = Paginator(products, 12).get_page(request.GET.get("page"))
        payload = {
            "items": list(page.object_list),
            "count": page.paginator.count,
            "number": page.number,
        }
        cache.set(key, payload, 60)
    page = Paginator(range(payload["count"]), 12).get_page(payload["number"])
    page.object_list = payload["items"]
    template = (
        "store/product_grid.html"
        if request.headers.get("HX-Request") == "true"
        else "store/catalog.html"
    )
    return render(
        request,
        template,
        {"page": page, "categories": Category.objects.all(), "q": query},
    )


@require_GET
def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    product = get_object_or_404(catalog_products(), slug=slug)
    variants = list(product.variants.all())
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.description,
        "offers": [
            {
                "@type": "Offer",
                "priceCurrency": "EGP",
                "price": str(v.price),
                "availability": (
                    "https://schema.org/InStock"
                    if v.stock
                    else "https://schema.org/OutOfStock"
                ),
                "url": request.build_absolute_uri(),
            }
            for v in variants
        ],
    }
    # Escape '<' to prevent product text from closing the JSON-LD script element.
    data = json.dumps(structured_data, ensure_ascii=False).replace("<", "\\u003c")
    return render(
        request,
        "store/detail.html",
        {"product": product, "variants": variants, "structured_data": data},
    )


def cart_lines(request: HttpRequest) -> tuple[list[dict[str, Any]], Decimal]:
    cart = request.session.get("cart", {})
    variants = Variant.objects.filter(pk__in=cart).select_related("product")
    lines = []
    total = Decimal("0.00")
    for variant in variants:
        count = cart[str(variant.pk)]
        subtotal = variant.price * count
        lines.append({"variant": variant, "quantity": count, "subtotal": subtotal})
        total += subtotal
    return lines, total


@require_GET
def cart_view(request: HttpRequest) -> HttpResponse:
    lines, total = cart_lines(request)
    return render(request, "store/cart.html", {"lines": lines, "total": total})


@require_POST
def cart_update(request: HttpRequest) -> HttpResponse:
    form = CartForm(request.POST)
    if not form.is_valid():
        return HttpResponse("الكمية غير صالحة.", status=400)
    variant = get_object_or_404(
        Variant.objects.select_related("product"), pk=form.cleaned_data["variant"]
    )
    quantity = form.cleaned_data["quantity"]
    if quantity and not variant.product.active:
        return HttpResponse("المنتج مش متاح دلوقتي.", status=400)
    if quantity > variant.stock:
        return HttpResponse("الكمية المطلوبة مش متاحة.", status=400)
    cart = request.session.get("cart", {}).copy()
    if quantity == 0:
        cart.pop(str(variant.pk), None)
    else:
        if str(variant.pk) not in cart and len(cart) >= 50:
            return HttpResponse("السلة وصلت للحد الأقصى.", status=400)
        cart[str(variant.pk)] = quantity
    request.session["cart"] = cart
    request.session.pop("checkout_key", None)
    return redirect("cart")


@require_http_methods(["GET", "POST"])
def checkout_view(request: HttpRequest) -> HttpResponse:
    if not request.session.session_key:
        request.session.create()
    if "checkout_key" not in request.session:
        request.session["checkout_key"] = str(uuid.uuid4())
    form = CheckoutForm(
        request.POST if request.method == "POST" else None,
        initial={"key": request.session["checkout_key"]},
    )
    if request.method == "POST" and form.is_valid():
        key = form.cleaned_data["key"]
        if str(key) != request.session["checkout_key"]:
            form.add_error(None, "الطلب اتغير. افتح صفحة الدفع تاني.")
        else:
            details = {k: v for k, v in form.cleaned_data.items() if k != "key"}
            try:
                order = checkout(
                    cart=request.session.get("cart", {}),
                    session_key=request.session.session_key or "",
                    key=key,
                    details=details,
                )
            except CheckoutError as exc:
                form.add_error(None, str(exc))
            else:
                request.session["cart"] = {}
                return redirect("order", order_id=order.pk)
    lines, total = cart_lines(request)
    return render(
        request,
        "store/checkout.html",
        {"form": form, "lines": lines, "total": total},
        status=400 if form.errors else 200,
    )


@require_GET
def order_detail(request: HttpRequest, order_id: uuid.UUID) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.prefetch_related("lines"),
        pk=order_id,
        session_key=request.session.session_key or "",
    )
    return render(request, "store/order.html", {"order": order})


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("health", True, 10)
        if not cache.get("health"):
            raise ConnectionError("Cache unavailable")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_GET
def robots(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        "User-agent: *\nDisallow: /admin/\nDisallow: /checkout/\n"
        "Disallow: /orders/\nSitemap: "
        + request.build_absolute_uri(reverse("sitemap"))
        + "\n",
        content_type="text/plain",
    )
