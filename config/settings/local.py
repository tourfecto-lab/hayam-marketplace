from django.core.management.utils import get_random_secret_key

from .base import *  # noqa: F403
from .base import BASE_DIR


def local_secret() -> str:
    path = BASE_DIR / ".local-secret"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(get_random_secret_key())
    except FileExistsError:
        pass
    return path.read_text(encoding="utf-8")


SECRET_KEY = local_secret()
DEBUG = True
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
