from django.db import models
from django.conf import settings
import uuid


class TicketRequest(models.Model):
    USER_TYPES = [
        ("volunteer", "Gönüllü"),
        ("scholar", "Bursiyer"),
        ("staff", "Personel"),
    ]
    TRANSPORT_TYPES = [
        ("bus", "Otobüs"),
        ("plane", "Uçak"),
    ]
    STATUS = [
        ("pending", "Beklemede"),
        ("ticketed", "Bilet Alındı"),
        ("rejected", "Bilet Reddedildi"),
    ]
    REASONS = [
        ("teknofest", "TEKNOFEST"),
        ("gorevlendirme", "Görevlendirme"),
        ("diger", "Diğer"),
    ]
    AIRLINES = [
        ("THY", "THY"),
        ("AJET", "AJet"),
        ("PEGASUS", "Pegasus"),
    ]

    tracking_code = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPES)

    # Kimlik/iletişim
    full_name = models.CharField(max_length=120)
    tc_no = models.CharField(max_length=11)
    phone = models.CharField(max_length=20)

    # Gidiş
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    travel_date = models.DateField()
    departure_time = models.TimeField(blank=True, null=True)  # opsiyonel

    # Dönüş (opsiyonel)
    return_destination = models.CharField(max_length=100, blank=True, null=True)
    return_date = models.DateField(blank=True, null=True)
    return_time = models.TimeField(blank=True, null=True)

    # Talep nedeni
    reason = models.CharField(max_length=20, choices=REASONS, default="teknofest")
    reason_other = models.CharField(max_length=200, blank=True, null=True)

    # Havayolu tercihi (opsiyonel, uçaksa anlamlı)
    preferred_airline = models.CharField(
        max_length=20, choices=AIRLINES, blank=True, null=True
    )

    transport = models.CharField(max_length=10, choices=TRANSPORT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    pnr_code = models.CharField(max_length=40, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Kaydı oluşturan (opsiyonel)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tickets",
    )
    # Bileti alan personel (opsiyonel)
    purchased_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_purchased",
        help_text="Bileti alan personel",
    )
    #  Reddeden kişi ve gerekçe (opsiyonel)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_rejected",
        help_text="Kaydı reddeden personel",
    )

    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_rejected"
    )
    rejection_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["tracking_code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["transport"]),
            models.Index(fields=["user_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["reason"]),
        ]

    def save(self, *args, **kwargs):
        if not self.tracking_code:
            # 12 karakterlik benzersiz kod
            self.tracking_code = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.origin}→{self.destination} ({self.travel_date})"


class ChangeRequest(models.Model):
    ticket = models.ForeignKey(
        TicketRequest,
        on_delete=models.CASCADE,
        related_name="changes",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Değişiklik Talebi: {self.ticket.tracking_code}"
