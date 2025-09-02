# tickets/sheets_sync.py
from __future__ import annotations

import time
from typing import List
from django.conf import settings
from django.utils.dateparse import parse_date

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

from .models import TicketRequest, ChangeRequest


SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Tek noktadan başlıklar
TICKETS_HEADERS = [
    "tracking_code",
    "user_type",
    "full_name",
    "tc_no",
    "phone",
    "origin",
    "destination",
    "travel_date",
    "departure_time",
    "return_destination",
    "return_date",
    "return_time",
    "reason",
    "reason_other",
    "preferred_airline",
    "transport",
    "status",
    "pnr_code",
    "created_at",
    "purchased_by",
    "rejected_by",
    "rejection_reason",
]

CHANGES_HEADERS = [
    "ticket_tracking_code",
    "reason",
    "created_at",
]


def _gc() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.SHEETS_CREDENTIALS_FILE, scopes=SCOPE
    )
    return gspread.authorize(creds)


def _ss(client: gspread.Client) -> gspread.Spreadsheet:
    if not settings.SHEETS_SPREADSHEET_ID:
        raise RuntimeError("SHEETS_SPREADSHEET_ID ayarı boş. .env içinde tanımlayın.")
    return client.open_by_key(settings.SHEETS_SPREADSHEET_ID)


def _safe_name(u):
    """Kullanıcı ad/soyadını güvenli üretmek için yardımcı."""
    if not u:
        return ""
    full = u.get_full_name()
    return full if full else u.username


def _tickets_matrix() -> List[List[str]]:
    """Django verilerinden TICKETS tablo matrisi üretir."""
    qs = (
        TicketRequest.objects
        .select_related("purchased_by", "rejected_by")
        .order_by("created_at")
    )

    rows = []
    for t in qs:
        rows.append([
            t.tracking_code,
            t.user_type,
            t.full_name,
            t.tc_no,
            t.phone,
            t.origin,
            t.destination,
            str(t.travel_date) if t.travel_date else "",
            str(t.departure_time) if t.departure_time else "",
            t.return_destination or "",
            str(t.return_date) if t.return_date else "",
            str(t.return_time) if t.return_time else "",
            t.reason or "",
            t.reason_other or "",
            t.preferred_airline or "",
            t.transport,
            t.status,
            t.pnr_code or "",
            str(t.created_at),
            _safe_name(t.purchased_by),
            _safe_name(t.rejected_by),
            (t.rejection_reason or ""),
        ])
    return rows


def _changes_matrix() -> List[List[str]]:
    qs = (
        ChangeRequest.objects
        .select_related("ticket")
        .order_by("created_at")
    )
    rows = []
    for c in qs:
        rows.append([
            c.ticket.tracking_code if c.ticket_id else "",
            c.reason or "",
            str(c.created_at),
        ])
    return rows


def _values_update_with_retry(spreadsheet: gspread.Spreadsheet, range_name: str, values: List[List[str]],
                              max_retries: int = 3, sleep_seconds: int = 60):
    """
    Google Sheets'e tek hamlede yaz. 429 (quota) gelirse bekleyip yeniden dene.
    """
    body = {"values": values}
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return spreadsheet.values_update(
                range_name,
                params={"valueInputOption": "RAW"},
                body=body,
            )
        except APIError as e:
            last_err = e
            # Sadece 429'da bekle, diğer hataları direkt yükselt
            if "429" in str(e):
                # Basit bekleme/log
                print(f"[sync] 429 Quota exceeded (deneme {attempt}/{max_retries}). {sleep_seconds}s bekleniyor...")
                time.sleep(sleep_seconds)
            else:
                raise
    # Hâlâ olmadı → hatayı yükselt
    raise last_err


def push_all():
    """
    Hiç okuma yapmadan:
      - Tickets sayfasını başlık + veri ile komple yazar,
      - Changes sayfasını başlık + veri ile komple yazar.
    Böylece READ kotasına takılmadan, tek/az sayıda WRITE ile biter.
    """
    client = _gc()
    ss = _ss(client)

    # Tickets
    tickets_values = [TICKETS_HEADERS] + _tickets_matrix()
    _values_update_with_retry(
        ss,
        f"{settings.SHEETS_TICKETS_WORKSHEET}!A1",
        tickets_values,
        max_retries=3,
        sleep_seconds=60,
    )

    # Changes
    changes_values = [CHANGES_HEADERS] + _changes_matrix()
    _values_update_with_retry(
        ss,
        f"{settings.SHEETS_CHANGES_WORKSHEET}!A1",
        changes_values,
        max_retries=3,
        sleep_seconds=60,
    )

    return {
        "tickets_rows": len(tickets_values) - 1,
        "changes_rows": len(changes_values) - 1,
    }
