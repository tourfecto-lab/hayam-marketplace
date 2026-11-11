from collections.abc import Callable
from hashlib import sha256

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and request.path in {"/admin/login/", "/checkout/"}:
            address = request.META.get("REMOTE_ADDR", "unknown")
            if settings.TRUST_PROXY:
                address = request.META.get("HTTP_X_FORWARDED_FOR", address)
            key = "rate:" + sha256((request.path + address).encode()).hexdigest()
            cache.add(key, 0, 300)
            if cache.incr(key) > 20:
                response = HttpResponse(
                    "محاولات كتير. استني ٥ دقايق وجربي تاني.", status=429
                )
                response["Retry-After"] = "300"
                return response
        response = self.get_response(request)
        response["Referrer-Policy"] = "same-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Admin ships inline scripts; the public storefront needs no inline JS.
        if not request.path.startswith("/admin/"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; script-src 'self'; "
                "style-src 'self'; frame-ancestors 'none'; "
                "base-uri 'self'; form-action 'self'"
            )
        return response
