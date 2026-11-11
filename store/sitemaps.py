from typing import Any

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self) -> Any:
        return Product.objects.filter(active=True).order_by("pk")

    def location(self, obj: Product) -> str:
        return reverse("product", args=[obj.slug])
