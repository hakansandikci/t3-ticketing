# tickets/views.py
from __future__ import annotations

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.utils.dateparse import parse_date

import csv
import logging
from openpyxl import Workbook

from .models import TicketRequest, ChangeRequest
from .forms import TicketRequestForm, ChangeRequestForm

logger = logging.getLogger(__name__)

# --- Sheet backend'i otomatik seç (önce Service Account, sonra Apps Script) ---
_gs = None
_apps = None
try:
    from tickets import gsheets as _gs  # Service Account tabanlı
except Exception:
    _gs = None

try:
    import sheets_api as _apps  # Apps Script WebApp tabanlı
except Exception:
    _apps = None


def _sheet_create(ticket) -> dict | None:
    """Yeni kayıt/insert. (gsheets: upsert, apps: create)"""
    if _gs:
        return _gs.upsert_ticket(ticket)
    if _apps:
        return _apps.create_ticket(ticket)
    logger.warning("Sheet backend bulunamadı (gsheets/sheets_api yok).")
    return None


def _sheet_update(ticket) -> dict | None:
    """Güncelleme/upsert."""
    if _gs:
        return _gs.upsert_ticket(ticket)
    if _apps:
        return _apps.update_ticket(ticket)
    logger.warning("Sheet backend bulunamadı (gsheets/sheets_api yok).")
    return None


def _sheet_change_append(change) -> dict | None:
    """Changes sekmesine ekle."""
    if _gs:
        return _gs.append_change(change)
    if _apps:
        return _apps.create_change(change)
    logger.warning("Sheet backend bulunamadı (gsheets/sheets_api yok).")
    return None


# -----------------------
# Ortak sabitler / yardımcılar
# -----------------------
EXPORT_FIELDS = [
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


def _row_for_export(t: TicketRequest):
    """CSV/XLSX satır oluşturur (tarih/saatleri string'e çevirir)."""
    return [
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
        t.reason,
        (t.reason_other or ""),
        (t.preferred_airline or ""),
        t.transport,
        t.status,
        (t.pnr_code or ""),
        str(t.created_at),
        (t.purchased_by.get_full_name() if t.purchased_by else ""),
        (t.rejected_by.get_full_name() if t.rejected_by else ""),
        (t.rejection_reason or ""),
    ]


# -----------------------
# Public views
# -----------------------
def home(request):
    return render(request, "home.html")


def request_create(request):
    if request.method == "POST":
        form = TicketRequestForm(request.POST)
        if form.is_valid():
            # 1) Önce DB'ye kaydet
            ticket = form.save(commit=False)
            if request.user.is_authenticated:
                ticket.created_by = request.user
            ticket.save()

            # 2) Sheet'e gönder (create/upsert)
            try:
                logger.warning("SHEETS -> create çağrılıyor: %s", ticket.tracking_code or "(boş)")
                resp = _sheet_create(ticket)
                logger.warning("SHEETS -> yanıt: %s", resp)

                # Apps Script tracking_code üretir ise geri yaz (Service Account'ta gerekmez)
                if (
                    not ticket.tracking_code
                    and isinstance(resp, dict)
                    and resp.get("tracking_code")
                ):
                    ticket.tracking_code = resp["tracking_code"]
                    ticket.save(update_fields=["tracking_code"])
            except Exception:
                logger.exception("Sheet create failed")

            # Formu sıfırla + popup için tracking_code ver
            return render(
                request,
                "request_create.html",
                {"form": TicketRequestForm(), "tracking_code": ticket.tracking_code},
            )
    else:
        form = TicketRequestForm()
    return render(request, "request_create.html", {"form": form})


def request_status_lookup(request):
    if request.method == "POST":
        code = request.POST.get("tracking_code", "").strip().upper()
        if not code:
            messages.error(request, "Takip kodu gerekli.")
            return redirect("tickets:status_lookup")
        return redirect("tickets:status_detail", tracking_code=code)
    return render(request, "status_lookup.html")


def request_status_detail(request, tracking_code):
    ticket = get_object_or_404(TicketRequest, tracking_code=tracking_code.upper())

    # Bilet alındı veya reddedildiyse değişiklik talebi açılamasın
    can_change = ticket.status not in ("ticketed", "rejected")
    change_form = None

    if can_change:
        if request.method == "POST":
            change_form = ChangeRequestForm(request.POST)
            if change_form.is_valid():
                change = change_form.save(commit=False)
                reason = (change.reason or "").strip()
                if not reason:
                    change_form.add_error("reason", "Lütfen talep metni girin.")
                else:
                    change.reason = reason
                    change.ticket = ticket
                    change.save()

                    # Sheets: Change append
                    try:
                        _sheet_change_append(change)
                    except Exception:
                        logger.exception("Sheet change append failed")

                    messages.success(request, "Değişiklik talebiniz alındı.")
                    return redirect("tickets:status_detail", tracking_code=tracking_code)
        else:
            change_form = ChangeRequestForm()

    # Revize listesi (son eklenen en üstte)
    changes = ticket.changes.order_by("-created_at")

    return render(
        request,
        "status_detail.html",
        {
            "ticket": ticket,
            "change_form": change_form,
            "can_change": can_change,
            "changes": changes,
        },
    )


# -----------------------
# Staff views
# -----------------------
def staff_check(user):
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(staff_check)
def staff_dashboard(request):
    q = (
        TicketRequest.objects.annotate(change_count=Count("changes"))
        .select_related("purchased_by", "created_by", "rejected_by")
        .prefetch_related(
            Prefetch("changes", queryset=ChangeRequest.objects.order_by("-created_at"))
        )
        .order_by("-updated_at", "-created_at")
    )

    # Serbest arama (takip kodu / ad soyad / PNR)
    qtext = request.GET.get("q")
    if qtext:
        q = q.filter(
            Q(tracking_code__icontains=qtext)
            | Q(full_name__icontains=qtext)
            | Q(pnr_code__icontains=qtext)
        )

    # Filtreler
    f_status = request.GET.get("status")
    f_transport = request.GET.get("transport")
    f_type = request.GET.get("user_type")
    f_has_changes = request.GET.get("has_changes")

    if f_status:
        q = q.filter(status=f_status)
    if f_transport:
        q = q.filter(transport=f_transport)
    if f_type:
        q = q.filter(user_type=f_type)
    if f_has_changes == "1":
        q = q.filter(change_count__gt=0)

    return render(request, "staff_dashboard.html", {"tickets": q})


@login_required
@user_passes_test(staff_check)
def staff_ticket_edit(request, pk):
    ticket = get_object_or_404(TicketRequest, pk=pk)

    if request.method == "POST":
        pnr = (request.POST.get("pnr_code") or "").strip()
        status = request.POST.get("status")

        # Opsiyonel (nadir) değişiklikler
        new_date_str = request.POST.get("travel_date")
        new_origin = (request.POST.get("origin") or "").strip()
        new_destination = (request.POST.get("destination") or "").strip()

        # Reddetme alanı
        rejection_reason = (request.POST.get("rejection_reason") or "").strip()

        valid_statuses = dict(TicketRequest.STATUS).keys()
        if status not in valid_statuses:
            return HttpResponseBadRequest("Geçersiz durum")

        # Kurallar
        if status == "ticketed" and not pnr:
            messages.error(request, "Bilet 'Alındı' durumunda PNR zorunludur.")
            return render(request, "staff_ticket_edit.html", {"ticket": ticket})

        if status == "rejected" and not rejection_reason:
            messages.error(
                request, "Reddedildi durumunda 'Red talebi / açıklama' zorunludur."
            )
            return render(
                request,
                "staff_ticket_edit.html",
                {
                    "ticket": ticket,
                    "posted_status": status,
                    "posted_pnr": pnr,
                    "posted_rejection_reason": rejection_reason,
                },
            )

        # Durumlara göre alanlar:
        ticket.status = status
        if status == "ticketed":
            ticket.pnr_code = pnr
            ticket.purchased_by = request.user
            ticket.rejected_by = None
            ticket.rejection_reason = None
        elif status == "rejected":
            ticket.pnr_code = None
            ticket.purchased_by = None
            ticket.rejected_by = request.user
            ticket.rejection_reason = rejection_reason
        else:  # pending
            ticket.pnr_code = pnr if pnr else None
            ticket.purchased_by = None
            ticket.rejected_by = None
            ticket.rejection_reason = None

        # Opsiyonel tarih/rota düzeltmeleri
        if new_date_str:
            parsed = parse_date(new_date_str)
            if parsed:
                ticket.travel_date = parsed
        if new_origin:
            ticket.origin = new_origin
        if new_destination:
            ticket.destination = new_destination

        ticket.save()

        # Sheets: UPDATE (upsert)
        try:
            _sheet_update(ticket)
        except Exception:
            logger.exception("Sheet update failed")

        messages.success(request, "Kayıt güncellendi.")
        return redirect(
            request.GET.get("next")
            or request.META.get("HTTP_REFERER")
            or "tickets:staff_dashboard"
        )

    return render(request, "staff_ticket_edit.html", {"ticket": ticket})


# -----------------------
# Reports / Exports
# -----------------------
@login_required
@user_passes_test(staff_check)
def export_csv(request):
    qs = (
        TicketRequest.objects.select_related("purchased_by", "rejected_by")
        .all()
        .order_by("-created_at")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="tickets.csv"'

    writer = csv.writer(response)
    writer.writerow(EXPORT_FIELDS)
    for t in qs:
        writer.writerow(_row_for_export(t))
    return response


@login_required
@user_passes_test(staff_check)
def export_xlsx(request):
    qs = (
        TicketRequest.objects.select_related("purchased_by", "rejected_by")
        .all()
        .order_by("-created_at")
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Tickets"

    ws.append(EXPORT_FIELDS)
    for t in qs:
        ws.append(_row_for_export(t))

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="tickets.xlsx"'
    wb.save(response)
    return response


@login_required
@user_passes_test(staff_check)
def reports(request):
    by_status = TicketRequest.objects.values("status").annotate(c=Count("id")).order_by()
    by_transport = (
        TicketRequest.objects.values("transport").annotate(c=Count("id")).order_by()
    )
    by_type = TicketRequest.objects.values("user_type").annotate(c=Count("id")).order_by()
    return render(
        request,
        "reports.html",
        {"by_status": by_status, "by_transport": by_transport, "by_type": by_type},
    )
