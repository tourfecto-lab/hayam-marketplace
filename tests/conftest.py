from collections.abc import Iterator
from typing import Any, cast

import factory
import pytest
from django.core.cache import cache

from store.models import Category, Product, Variant


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = "عبايات"
    slug = factory.Sequence(lambda n: f"category-{n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    category = factory.SubFactory(CategoryFactory)
    name = "عباية مريحة"
    slug = factory.Sequence(lambda n: f"product-{n}")
    description = "خامة ناعمة ومقاس مريح"
    active = True


class VariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Variant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n}")
    size = "XL"
    color = "أسود"
    price = "125.55"
    stock = 10


@pytest.fixture(autouse=True)
def clean_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def variant(db: Any) -> Variant:
    return cast(Variant, VariantFactory())
