# tickets/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import TicketRequest, ChangeRequest

# Sheets ile konuşan fonksiyonları içe al
# upsert_ticket: Tickets sayfasında ilgili tracking_code satırını (varsa günceller, yoksa ekler)
# append_change: Changes sayfasına yeni bir satır ekler
try:
    from .sheets_sync import upsert_ticket, append_change
except Exception:
    # deploy sırasında import hatası olursa app ayakta kalsın
    upsert_ticket = None
    append_change = None


@receiver(post_save, sender=TicketRequest)
def push_ticket_to_sheet(sender, instance: TicketRequest, created, **kwargs):
    # Sheets entegrasyonu kapalıysa çalışmasın
    if not getattr(settings, "SHEETS_SPREADSHEET_ID", ""):
        return
    if upsert_ticket is None:
        return

    try:
        upsert_ticket(instance)  # anlık olarak ilgili satırı yaz/güncelle
    except Exception as e:
        # loglamak istersen:
        # import logging; logging.getLogger(__name__).exception("Sheets push error: %s", e)
        pass


@receiver(post_save, sender=ChangeRequest)
def push_change_to_sheet(sender, instance: ChangeRequest, created, **kwargs):
    if not created:
        return  # değişiklik kaydı sadece ilk oluştuğunda yazılsın
    if not getattr(settings, "SHEETS_SPREADSHEET_ID", ""):
        return
    if append_change is None:
        return

    try:
        append_change(instance)  # Changes sayfasına yeni satır
    except Exception:
        pass
