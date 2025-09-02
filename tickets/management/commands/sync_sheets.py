# tickets/management/commands/sync_sheets.py
from django.core.management.base import BaseCommand
from tickets.sheets_sync import push_all


class Command(BaseCommand):
    help = "Google Sheets ile toplu senkronizasyon (tam tablo yazma)."

    def handle(self, *args, **options):
        out = push_all()
        self.stdout.write(
            self.style.SUCCESS(
                f"Senkron tamamlandı. Tickets: {out['tickets_rows']} satır, Changes: {out['changes_rows']} satır."
            )
        )
