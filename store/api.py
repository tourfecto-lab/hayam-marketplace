from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny

from .models import Product, Variant
from .views import catalog_products


class VariantSerializer(serializers.ModelSerializer[Variant]):
    class Meta:
        model = Variant
        fields = ["id", "size", "color", "price", "stock"]


class ProductSerializer(serializers.ModelSerializer[Product]):
    variants = VariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "description", "variants"]


class ProductViewSet(viewsets.ReadOnlyModelViewSet[Product]):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    queryset = catalog_products()
    lookup_field = "slug"
