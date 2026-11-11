from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import Category, Product, Variant


class Command(BaseCommand):
    help = "Seed repeatable Arabic demo products without changing existing stock."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        groups = [
            ("abayas", "عبايات", "عباية كريب واسعة", "790.00"),
            ("isdals", "إسدالات", "إسدال صلاة قطن", "450.00"),
            ("nightwear", "ملابس بيت", "بيجامة قطن ناعمة", "520.00"),
            ("plus-size", "مقاسات كبيرة", "طقم بيت مريح مقاس كبير", "650.00"),
        ]
        for slug, category_name, name, price in groups:
            category, _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": category_name}
            )
            product, _ = Product.objects.get_or_create(
                slug=slug + "-demo",
                defaults={
                    "category": category,
                    "name": name,
                    "description": "خامة مريحة وقصة واسعة تناسب يومك. "
                    "راجعي المقاس واللون قبل الطلب.",
                    "active": True,
                },
            )
            for size in ("L", "XL", "2XL", "3XL"):
                for color in ("أسود", "كشمير"):
                    Variant.objects.get_or_create(
                        sku=f"{slug}-{size}-{color}",
                        defaults={
                            "product": product,
                            "size": size,
                            "color": color,
                            "price": price,
                            "stock": 12,
                        },
                    )
        self.stdout.write(self.style.SUCCESS("Arabic demo catalog seeded."))
