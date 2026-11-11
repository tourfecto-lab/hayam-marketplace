from typing import Any

from django.contrib import admin, messages
from django.http import HttpRequest

from .models import (
    Category,
    Notification,
    Order,
    OrderEvent,
    OrderLine,
    Product,
    ProductImage,
    Variant,
)
from .services import CheckoutError, transition_order


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 1


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ["thumbnail"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "active"]
    list_filter = ["active", "category"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [VariantInline, ImageInline]


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False


class LineInline(ReadOnlyInline):
    model = OrderLine


class EventInline(ReadOnlyInline):
    model = OrderEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "phone", "status", "total", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["phone", "name"]
    readonly_fields = [field.name for field in Order._meta.fields]
    inlines = [LineInline, EventInline]
    actions = [
        "mark_paid",
        "mark_shipped",
        "mark_delivered",
        "mark_cancelled",
        "mark_returned",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False

    def move(self, request: HttpRequest, queryset: Any, target: str) -> None:
        for order in queryset:
            try:
                transition_order(order.pk, target)
            except CheckoutError as exc:
                self.message_user(request, str(exc), messages.ERROR)

    @admin.action(description="Mark paid", permissions=["change"])
    def mark_paid(self, request: HttpRequest, queryset: Any) -> None:
        self.move(request, queryset, Order.Status.PAID)

    @admin.action(description="Mark shipped (including COD)", permissions=["change"])
    def mark_shipped(self, request: HttpRequest, queryset: Any) -> None:
        self.move(request, queryset, Order.Status.SHIPPED)

    @admin.action(description="Mark delivered", permissions=["change"])
    def mark_delivered(self, request: HttpRequest, queryset: Any) -> None:
        self.move(request, queryset, Order.Status.DELIVERED)

    @admin.action(description="Cancel and restore stock", permissions=["change"])
    def mark_cancelled(self, request: HttpRequest, queryset: Any) -> None:
        self.move(request, queryset, Order.Status.CANCELLED)

    @admin.action(
        description="Accept returned goods and restore stock", permissions=["change"]
    )
    def mark_returned(self, request: HttpRequest, queryset: Any) -> None:
        self.move(request, queryset, Order.Status.RETURNED)


admin.site.register(Category)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "event", "sent_at", "attempts"]
    readonly_fields = ["event", "sent_at", "attempts"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Notification | None = None
    ) -> bool:
        return False
