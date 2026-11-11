from django.apps import AppConfig


class StoreConfig(AppConfig):
    name = "store"

    def ready(self) -> None:
        from . import signals  # noqa: F401
