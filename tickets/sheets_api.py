# tickets/sheets_api.py
import os
import json
import logging
from decimal import Decimal
from django.conf import settings

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = settings.GOOGLE_SHEETS_SPREADSHEET_ID
TICKETS_SHEET = "Tickets"
CHANGES_SHEET = "Changes"

# Tickets başlıkları: Sheet 1. satırla birebir aynı sıra!
HEADERS = [
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

def _creds():
    """Service Account cred'lerini hem FILE hem INFO'dan destekle."""
    if getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", ""):
        return Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
    if getattr(settings, "GOOGLE_SERVICE_ACCOUNT_INFO", ""):
        info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_INFO)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    raise RuntimeError("Service Account bilgisi yok. .env ayarlarını kontrol et.")

def _service():
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)

def _to_str(x):
    if x is None:
        return ""
    if isinstance(x, Decimal):
        return float(x)
    return str(x)

def _row_from_ticket(t):
    """Model -> Sheet satırı (HEADERS sırasına göre)."""
    get = {
        "tracking_code": lambda: t.tracking_code,
        "user_type": lambda: t.user_type,
        "full_name": lambda: t.full_name,
        "tc_no": lambda: t.tc_no,
        "phone": lambda: t.phone,
        "origin": lambda: t.origin,
        "destination": lambda: t.destination,
        "travel_date": lambda: t.travel_date or "",
        "departure_time": lambda: t.departure_time or "",
        "return_destination": lambda: t.return_destination or "",
        "return_date": lambda: t.return_date or "",
        "return_time": lambda: t.return_time or "",
        "reason": lambda: t.reason,
        "reason_other": lambda: t.reason_other or "",
        "preferred_airline": lambda: t.preferred_airline or "",
        "transport": lambda: t.transport,
        "status": lambda: t.status,
        "pnr_code": lambda: t.pnr_code or "",
        "created_at": lambda: t.created_at,  # datetime; str() ile ISO gibi gidecek
        "purchased_by": lambda: (t.purchased_by.get_full_name() if t.purchased_by else ""),
        "rejected_by": lambda: (t.rejected_by.get_full_name() if getattr(t, "rejected_by", None) else ""),
        "rejection_reason": lambda: (t.rejection_reason or "") if hasattr(t, "rejection_reason") else "",
    }
    return [_to_str(get[k]()) for k in HEADERS]

def _col_letter(n: int) -> str:
    """1->A, 26->Z, 27->AA ..."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _find_ticket_row_index(service, tracking_code: str) -> int:
    """Tracking code'un satır numarasını bul (yoksa -1)."""
    if not tracking_code:
        return -1
    col = "A"  # tracking_code = A sütunu varsayımı
    rng = f"{TICKETS_SHEET}!{col}2:{col}"  # A2:A
    res = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=rng
    ).execute()
    vals = res.get("values", [])
    for i, row in enumerate(vals, start=2):
        if row and str(row[0]).strip().upper() == str(tracking_code).strip().upper():
            return i
    return -1

# --------- Public API (views.py bunları çağırıyor) ---------

def create_ticket(ticket):
    """Yeni satır ekle. tracking_code boşsa olduğu gibi yazar (otomatik üretim gerekiyorsa Django tarafında)."""
    srv = _service()
    body = {"values": [_row_from_ticket(ticket)]}
    res = srv.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{TICKETS_SHEET}!A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()
    logger.warning("Sheets APPEND: %s", res)
    # Service API tracking_code üretmez; Apps Script'teki gibi geri dönmüyoruz.
    return {"ok": True}

def update_ticket(ticket):
    """tracking_code'a göre satırı güncelle; yoksa append (upsert)."""
    srv = _service()
    row_idx = _find_ticket_row_index(srv, ticket.tracking_code)
    values = [_row_from_ticket(ticket)]
    last_col = _col_letter(len(HEADERS))  # 22 -> 'V'
    if row_idx == -1:
        # yoksa ekle
        res = srv.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{TICKETS_SHEET}!A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        logger.warning("Sheets UPSERT(APPEND): %s", res)
        return {"ok": True, "appended": True}
    else:
        # var olan satırı güncelle
        rng = f"{TICKETS_SHEET}!A{row_idx}:{last_col}{row_idx}"
        res = srv.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=rng,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
        logger.warning("Sheets UPDATE row=%s: %s", row_idx, res)
        return {"ok": True, "updated": True, "row": row_idx}

def create_change(change):
    """Changes sheet'ine basit append."""
    srv = _service()
    vals = [[
        str(change.ticket.tracking_code),
        str(change.reason or ""),
        _to_str(change.created_at),
    ]]
    res = srv.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{CHANGES_SHEET}!A:C",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": vals},
    ).execute()
    logger.warning("Sheets CHANGE APPEND: %s", res)
    return {"ok": True}
