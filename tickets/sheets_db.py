# tickets/sheets_db.py
import os, time, uuid
from datetime import datetime
from functools import wraps

import gspread
from google.oauth2.service_account import Credentials

# ====== Bağlantı / yardımcılar ======
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.getenv("SHEETS_SPREADSHEET_ID")

def _gc():
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def _ws(title: str):
    return _gc().open_by_key(SPREADSHEET_ID).worksheet(title)

def backoff(retries=6, base=0.4, factor=1.7):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            delay = base
            for i in range(retries):
                try:
                    return fn(*a, **kw)
                except Exception:
                    if i == retries - 1:
                        raise
                    time.sleep(delay)
                    delay *= factor
        return wrap
    return deco

# ====== Şema ======
TICKET_FIELDS = [
    "tracking_code","user_type","full_name","tc_no","phone",
    "origin","destination","travel_date","departure_time",
    "return_destination","return_date","return_time",
    "reason","reason_other","preferred_airline",
    "transport","status","pnr_code","notes",
    "created_by_email","purchased_by_email","purchased_by_name",
    "created_at","updated_at","rejected_by_email","reject_reason",
]

@backoff()
def _headers_map(ws):
    heads = ws.row_values(1)
    return {h: i+1 for i, h in enumerate(heads)}  # 1-based

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def _gen_tracking():
    return uuid.uuid4().hex[:12].upper()

@backoff()
def _find_row_by_tracking(ws, tracking_code: str):
    hm = _headers_map(ws)
    col = hm.get("tracking_code")
    if not col:
        raise RuntimeError("tickets sayfasında 'tracking_code' başlığı yok.")
    values = ws.col_values(col)
    # Satırlar 1’den başlar; 1 başlık, 2.. data
    for idx, val in enumerate(values, start=1):
        if idx == 1:  # başlığı geç
            continue
        if val == tracking_code:
            return idx
    return None

# ====== CREATE ======
@backoff()
def tickets_create(data: dict) -> str:
    """
    data: Django formundan temizlenmiş sözlük.
    Gerekli minimumlar: user_type, full_name, tc_no, phone, origin, destination, travel_date, transport, status
    """
    ws = _ws("tickets")
    tracking = data.get("tracking_code") or _gen_tracking()
    created_at = _now()
    updated_at = created_at

    # alanları sıraya göre doldur
    row = []
    for k in TICKET_FIELDS:
        if k == "tracking_code": row.append(tracking); continue
        if k == "created_at":   row.append(created_at); continue
        if k == "updated_at":   row.append(updated_at); continue
        row.append("" if data.get(k) is None else str(data.get(k)))

    ws.append_row(row)
    return tracking

# ====== READ (listeleme + filtre) ======
@backoff()
def tickets_list(filters: dict | None = None, q: str | None = None) -> list[dict]:
    """
    filters: {'status':'pending', 'transport':'plane', 'user_type':'staff', 'has_changes':True}
    q: basit arama (full_name, tracking_code, pnr_code)
    """
    ws = _ws("tickets")
    hm = _headers_map(ws)
    all_rows = ws.get_all_records()  # list[dict]

    def ok(rec: dict):
        if filters:
            if "status" in filters and filters["status"]:
                if rec.get("status") != filters["status"]: return False
            if "transport" in filters and filters["transport"]:
                if rec.get("transport") != filters["transport"]: return False
            if "user_type" in filters and filters["user_type"]:
                if rec.get("user_type") != filters["user_type"]: return False
        if q:
            ql = q.lower()
            hit = False
            for key in ("full_name","tracking_code","pnr_code"):
                val = (rec.get(key) or "")
                if ql in val.lower():
                    hit = True; break
            if not hit: return False
        return True

    # NOT: has_changes filtresi changes sayfasından sayım istiyorsa,
    # bunu view’de ayrı bir map ile birleştirmeni öneririm (örn. tracking_code -> adet).
    rows = [r for r in all_rows if ok(r)]

    # updated_at DESC, created_at DESC (string karşılaştırma ama ISO format olduğu için iş görür)
    rows.sort(key=lambda r: (r.get("updated_at",""), r.get("created_at","")), reverse=True)
    return rows

# ====== READ (tek kayıt) ======
@backoff()
def tickets_get(tracking_code: str) -> dict | None:
    ws = _ws("tickets")
    idx = _find_row_by_tracking(ws, tracking_code)
    if not idx:
        return None
    # A:Z aralığını geniş tutuyoruz (başlık sayısına göre)
    values = ws.row_values(idx)
    heads = ws.row_values(1)
    rec = {h: (values[i] if i < len(values) else "") for i, h in enumerate(heads)}
    return rec

# ====== UPDATE ======
@backoff()
def tickets_update(tracking_code: str, **fields):
    ws = _ws("tickets")
    hm = _headers_map(ws)
    row_idx = _find_row_by_tracking(ws, tracking_code)
    if not row_idx:
        return False
    updates = []
    for k, v in fields.items():
        if k not in hm:
            continue
        a1 = gspread.utils.rowcol_to_a1(row_idx, hm[k])
        updates.append({"range": a1, "values": [[("" if v is None else str(v))]]})
    if "updated_at" in hm:
        a1 = gspread.utils.rowcol_to_a1(row_idx, hm["updated_at"])
        updates.append({"range": a1, "values": [[ _now() ]]})
    if updates:
        ws.batch_update(updates)
    return True

# ====== CHANGES ======
@backoff()
def changes_append(tracking_code: str, change_text: str):
    ws = _ws("changes")
    ws.append_row([tracking_code, change_text, _now()])
