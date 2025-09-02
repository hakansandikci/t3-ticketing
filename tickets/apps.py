# tickets/apps.py
from django.apps import AppConfig
import os

class TicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tickets"

    def ready(self):
        # İstersen ileride sinyalleri tekrar açmak için
        # ortam değişkeniyle kontrol edilebilir yapıyoruz.
        if os.getenv("TICKETS_ENABLE_SIGNALS") == "1":
            from . import signals  # noqa
