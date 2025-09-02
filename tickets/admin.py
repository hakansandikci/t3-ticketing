
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import TicketRequest, ChangeRequest


class ChangeRequestInline(admin.TabularInline):
    model = ChangeRequest
    extra = 0
    readonly_fields = ("reason", "created_at")
    can_delete = False


@admin.register(TicketRequest)
class TicketRequestAdmin(admin.ModelAdmin):
    # Liste görünümü
    list_display = (
        "tracking_code",
        "full_name",
        "route_badge",
        "travel_date",
        "transport",
        "status_badge",
        "pnr_code",
        "purchased_by",
        "rejected_by",
    )
    list_filter = (
        "status",
        "transport",
        "user_type",
        "preferred_airline",
        "reason",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "tracking_code",
        "full_name",
        "tc_no",
        "phone",
        "origin",
        "destination",
        "pnr_code",
    )
    date_hierarchy = "created_at"
    ordering = ("-updated_at", "-created_at")

    # Okunur alanlar
    readonly_fields = ("tracking_code", "created_by", "created_at", "updated_at")

    inlines = [ChangeRequestInline]

    # Form düzeni
    fieldsets = (
        ("Başvuru Sahibi", {
            "fields": ("user_type", "full_name", "tc_no", "phone")
        }),
        ("Gidiş Bilgisi", {
            "fields": (("origin", "destination"), ("travel_date", "departure_time"))
        }),
        ("Dönüş (Opsiyonel)", {
            "classes": ("collapse",),
            "fields": (("return_destination", "return_date", "return_time"),)
        }),
        ("Talep ve Tercihler", {
            "fields": (("reason", "reason_other"), ("transport", "preferred_airline"))
        }),
        ("Durum / PNR", {
            "fields": (("status", "pnr_code"), ("purchased_by", "rejected_by"), "rejection_reason")
        }),
        ("Diğer", {
            "fields": ("notes",)
        }),
        ("Sistem", {
            "classes": ("collapse",),
            "fields": ("tracking_code", "created_by", "created_at", "updated_at")
        }),
    )

    # Renkli rozetler
    @admin.display(description="Rota")
    def route_badge(self, obj: TicketRequest):
        return format_html(
            '<span style="padding:.2rem .45rem; border-radius:.5rem; background:#F3F4F6; font-weight:600;">{} → {}</span>',
            obj.origin, obj.destination
        )

    @admin.display(description="Durum")
    def status_badge(self, obj: TicketRequest):
        color = {
            "pending":   ("#111827", "#E5E7EB"),   # gri
            "ticketed":  ("#065F46", "#D1FAE5"),   # yeşil
            "rejected":  ("#991B1B", "#FEE2E2"),   # kırmızı
        }.get(obj.status, ("#111827", "#E5E7EB"))
        fg, bg = color
        return format_html(
            '<span style="padding:.2rem .45rem; border-radius:.5rem; color:{}; background:{}; font-weight:700;">{}</span>',
            fg, bg, obj.get_status_display()
        )

    # Kaydetmede kuralları uygula
    def save_model(self, request, obj: TicketRequest, form, change):
        """
        - status=ticketed ise PNR zorunlu ve purchased_by otomatik bu kullanıcıya çekilir.
        - status=rejected ise rejection_reason zorunlu ve rejected_by otomatik atanır.
        - status=pending ise PNR/assigned alanları sıfırlanır.
        """
        # Talep nedeni "diğer" değilse metnini temizleyelim
        if obj.reason != "diger":
            obj.reason_other = None

        # Transport uçak değilse airline tercihini temizleyelim
        if obj.transport != "plane":
            obj.preferred_airline = None

        if obj.status == "ticketed":
            if not obj.pnr_code:
                messages.error(request, "‘Bilet Alındı’ durumunda PNR zorunludur.")
                # Mesaj verip yine de kaydedilirse, ValidationError yerine kullanıcıyı uyarıyoruz
                # İsterseniz Exception raise edebilirsiniz:
                # raise ValidationError("PNR zorunludur")
            obj.purchased_by = request.user
            obj.rejected_by = None
            obj.rejection_reason = None

        elif obj.status == "rejected":
            if not obj.rejection_reason:
                messages.error(request, "‘Reddedildi’ durumunda açıklama (red talebi) zorunludur.")
            obj.pnr_code = None
            obj.purchased_by = None
            obj.rejected_by = request.user

        else:  # pending
            # klasik beklemede
            if not obj.pnr_code:
                obj.pnr_code = None
            obj.purchased_by = None
            obj.rejected_by = None
            obj.rejection_reason = None

        super().save_model(request, obj, form, change)
        # Kullanıcıya özet bilgi
        if obj.status == "ticketed":
            messages.success(request, mark_safe(f"PNR <b>{obj.pnr_code or '—'}</b> ile ‘Bilet Alındı’ olarak kaydedildi."))
        elif obj.status == "rejected":
            messages.warning(request, "Talep ‘Reddedildi’ olarak kaydedildi.")
        else:
            messages.info(request, "Talep ‘Beklemede’ olarak kaydedildi.")


@admin.register(ChangeRequest)
class ChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("ticket", "created_at_short", "reason_excerpt")
    search_fields = ("ticket__tracking_code", "ticket__full_name", "reason")
    readonly_fields = ("ticket", "reason", "created_at")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Revizeler kullanıcıdan gelir; admin’den manuel eklemeyi kapatmak isteyebilirsiniz.
        return False

    @admin.display(description="Tarih/Saat")
    def created_at_short(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")

    @admin.display(description="Metin")
    def reason_excerpt(self, obj):
        txt = (obj.reason or "").strip()
        return (txt[:60] + "…") if len(txt) > 60 else txt
