import uuid
from decimal import Decimal
from typing import Any

from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    active = models.BooleanField(default=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Variant(models.Model):
    product = models.ForeignKey(
        Product, related_name="variants", on_delete=models.CASCADE
    )
    sku = models.CharField(max_length=80, unique=True)
    size = models.CharField(max_length=30)
    color = models.CharField(max_length=50)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"], name="unique_product_options"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="positive_price"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} / {self.size} / {self.color}"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, related_name="images", on_delete=models.CASCADE
    )
    image = models.ImageField(upload_to="products/")
    thumbnail = models.ImageField(upload_to="thumbnails/", blank=True)
    alt = models.CharField(max_length=200)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.image and not self.image._committed:
            from .uploads import prepare_image

            self.image, self.thumbnail = prepare_image(self.image)
        super().save(*args, **kwargs)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "قيد التأكيد"
        PAID = "paid", "تم الدفع"
        SHIPPED = "shipped", "تم الشحن"
        DELIVERED = "delivered", "تم التوصيل"
        CANCELLED = "cancelled", "ملغي"
        RETURNED = "returned", "مرتجع"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkout_key = models.UUIDField(unique=True)
    session_key = models.CharField(max_length=64, db_index=True, editable=False)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=14)
    email = models.EmailField(blank=True)
    address = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    currency = models.CharField(max_length=3, default="EGP", editable=False)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    options = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="positive_order_quantity"
            )
        ]


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, related_name="events", on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    event = models.OneToOneField(OrderEvent, on_delete=models.PROTECT)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
