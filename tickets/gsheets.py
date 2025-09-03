# tickets/gsheets.py
from __future__ import annotations
import os, json, base64, string
from typing import Dict, Any, List
from django.conf import settings
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import logging


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
logger = logging.getLogger(__name__)
def _load_sa_info() -> dict:
    """
    Service Account bilgilerini şu sırayla dener:
    1) GOOGLE_SERVICE_ACCOUNT_INFO_B64  (base64 JSON)
    2) GOOGLE_SERVICE_ACCOUNT_INFO      (düz JSON string)
    3) GOOGLE_SERVICE_ACCOUNT_FILE      (dosya yolu)
    """
    info_b64 = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_INFO_B64", "").strip()
    logger.warning(info_b64)
    if info_b64:
        return json.loads(base64.b64decode(info_b64).decode("utf-8"))

    info_raw = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_INFO", "").strip()
    if info_raw:
        return json.loads(info_raw)

    path = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if path:
        path = os.path.expandvars(os.path.expanduser(path))
        if not os.path.exists(path):
            raise RuntimeError(f"Service Account dosyası bulunamadı: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError("Service Account bilgisi bulunamadı. .env ayarlarını kontrol et.")

def _creds():
    info = _load_sa_info()
    return Credentials.from_service_account_info(info, scopes=SCOPES)

def service():
    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)

def _ssid() -> str:
    ssid = getattr(settings, "GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
    if not ssid:
        raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID tanımsız!")
    return ssid

def _tickets_sheet() -> str:
    return getattr(settings, "SHEETS_TICKETS_WORKSHEET", "Tickets")

def _changes_sheet() -> str:
    return getattr(settings, "SHEETS_CHANGES_WORKSHEET", "Changes")

def _col_to_a1(n: int) -> str:
    letters = []
    while n:
        n, rem = divmod(n - 1, 26)
        letters.append(string.ascii_uppercase[rem])
    return "".join(reversed(letters))

def get_headers(sheet_name: str) -> List[str]:
    srv = service()
    resp = srv.spreadsheets().values().get(
        spreadsheetId=_ssid(), range=f"{sheet_name}!1:1"
    ).execute()
    return (resp.get("values", [[]]) or [[]])[0]

def append_by_headers(sheet_name: str, values: Dict[str, Any]) -> dict:
    headers = get_headers(sheet_name)
    row = ["" for _ in headers]
    for i, h in enumerate(headers):
        v = values.get(str(h).strip(), "")
        row[i] = "" if v is None else str(v)
    srv = service()
    return srv.spreadsheets().values().append(
        spreadsheetId=_ssid(),
        range=f"{sheet_name}!A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values":[row]},
    ).execute()

def upsert_by_tracking(sheet_name: str, values: Dict[str, Any], tracking_key: str="tracking_code") -> dict:
    headers = get_headers(sheet_name)
    header_map = {str(h).strip(): idx+1 for idx, h in enumerate(headers)}
    if tracking_key not in header_map:
        raise RuntimeError(f"Sheet '{sheet_name}' içinde '{tracking_key}' başlığı yok.")

    col_idx = header_map[tracking_key]
    col_a1 = _col_to_a1(col_idx)

    srv = service()
    resp = srv.spreadsheets().values().get(
        spreadsheetId=_ssid(), range=f"{sheet_name}!{col_a1}2:{col_a1}"
    ).execute()
    col_vals = [r[0] if r else "" for r in resp.get("values", [])]

    target = str(values.get(tracking_key, "")).strip()
    row_index = None
    for i, val in enumerate(col_vals, start=2):
        if str(val).strip().upper() == target.upper():
            row_index = i
            break

    row = ["" for _ in headers]
    for i, h in enumerate(headers):
        v = values.get(str(h).strip(), "")
        row[i] = "" if v is None else str(v)

    if row_index is None:
        return srv.spreadsheets().values().append(
            spreadsheetId=_ssid(),
            range=f"{sheet_name}!A:Z",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values":[row]},
        ).execute()
    else:
        last_col_a1 = _col_to_a1(len(headers))
        return srv.spreadsheets().values().update(
            spreadsheetId=_ssid(),
            range=f"{sheet_name}!A{row_index}:{last_col_a1}{row_index}",
            valueInputOption="USER_ENTERED",
            body={"values":[row]},
        ).execute()

def ticket_to_dict(ticket) -> Dict[str, Any]:
    return {
        "tracking_code": t.tracking_code,
        "user_type": t.user_type,
        "full_name": t.full_name,
        "email": t.email or "",
        "birth_date": t.birth_date.isoformat() if t.birth_date else "",
        "tc_no": t.tc_no or "",
        "phone": t.phone or "",
        "origin": t.origin or "",
        "destination": t.destination or "",
        "travel_date": str(t.travel_date) if t.travel_date else "",
        "departure_time": str(t.departure_time) if t.departure_time else "",
        "return_destination": t.return_destination or "",
        "return_date": str(t.return_date) if t.return_date else "",
        "return_time": str(t.return_time) if t.return_time else "",
        "reason": t.reason or "",
        "reason_other": t.reason_other or "",
        "preferred_airline": t.preferred_airline or "",
        "flight_number": t.flight_number or "",
        "transport": t.transport or "",
        "status": t.status,
        "pnr_code": t.pnr_code or "",
        "created_at": str(t.created_at),
        "purchased_by": t.purchased_by.get_full_name() if t.purchased_by else "",
        "rejected_by": t.rejected_by.get_full_name() if getattr(t, "rejected_by", None) else "",
        "rejection_reason": (t.rejection_reason or "") if hasattr(t, "rejection_reason") else "",
        "trip_type": t.trip_type,
    }

def upsert_ticket(ticket) -> dict:
    return upsert_by_tracking(_tickets_sheet(), ticket_to_dict(ticket))

def append_change(change) -> dict:
    srv = service()
    return srv.spreadsheets().values().append(
        spreadsheetId=_ssid(),
        range=f"{_changes_sheet()}!A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values":[[
            change.ticket.tracking_code,
            change.reason,
            str(change.created_at),
        ]]},
    ).execute()
