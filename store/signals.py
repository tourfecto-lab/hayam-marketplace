from typing import Any
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .models import Category, Product, ProductImage, Variant


def invalidate_catalog(**kwargs: Any) -> None:
    transaction.on_commit(lambda: cache.set("catalog-version", uuid4().hex, None))


for model in (Category, Product, ProductImage, Variant):
    post_save.connect(invalidate_catalog, sender=model, weak=False)
    post_delete.connect(invalidate_catalog, sender=model, weak=False)
