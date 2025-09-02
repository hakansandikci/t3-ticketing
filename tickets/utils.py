# tickets/utils.py
def ticket_to_sheet_payload(t):
    """Sheet başlıklarıyla bire bir eşleşen dict üret."""
    return {
        "tracking_code": t.tracking_code,
        "user_type": t.user_type,
        "full_name": t.full_name,
        "tc_no": t.tc_no,
        "phone": t.phone,
        "origin": t.origin,
        "destination": t.destination,
        "travel_date": str(t.travel_date) if t.travel_date else "",
        "departure_time": str(t.departure_time) if t.departure_time else "",
        "return_destination": t.return_destination or "",
        "return_date": str(t.return_date) if t.return_date else "",
        "return_time": str(t.return_time) if t.return_time else "",
        "reason": t.reason,
        "reason_other": t.reason_other or "",
        "preferred_airline": t.preferred_airline or "",
        "transport": t.transport,
        "status": t.status,
        "pnr_code": t.pnr_code or "",
        "created_at": str(t.created_at),
        "purchased_by": (t.purchased_by.get_full_name() if getattr(t, "purchased_by", None) else ""),
        "rejected_by": (t.rejected_by.get_full_name() if getattr(t, "rejected_by", None) else ""),
        "rejection_reason": getattr(t, "rejection_reason", "") or "",
    }
