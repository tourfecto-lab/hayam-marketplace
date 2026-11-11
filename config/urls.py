from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from store import views
from store.api import ProductViewSet
from store.sitemaps import ProductSitemap

router = DefaultRouter()
router.register("products", ProductViewSet)
urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("products/<slug:slug>/", views.product_detail, name="product"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/update/", views.cart_update, name="cart-update"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("orders/<uuid:order_id>/", views.order_detail, name="order"),
    path("health/", views.health, name="health"),
    path("robots.txt", views.robots, name="robots"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": {"products": ProductSitemap}},
        name="sitemap",
    ),
    path("api/", include(router.urls)),
    path("admin/", admin.site.urls),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
