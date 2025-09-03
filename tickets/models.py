from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, MinLengthValidator
import uuid


class Option(models.Model):
    """Dropdown seçeneklerini dinamik yönetmek için tablo"""
    CATEGORY_CHOICES = [
        ("user_type", "Kullanıcı Türü"),
        ("transport", "Ulaşım Türü"),
        ("reason", "Talep Nedeni"),
        ("airline", "Havayolu"),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.get_category_display()} → {self.value}"


class TicketRequest(models.Model):
    STATUS = [
        ("pending", "Beklemede"),
        ("ticketed", "Bilet Alındı"),
        ("rejected", "Bilet Reddedildi"),
    ]
    TRIP_TYPES = [
        ("oneway", "Tek yön"),
        ("roundtrip", "Gidiş - Dönüş"),
    ]

    tracking_code = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
    )

    # Dinamik dropdownlar (Option tablosundan doldurulacak)
    user_type = models.CharField(max_length=50)
    transport = models.CharField(max_length=50)
    reason = models.CharField(max_length=50)
    preferred_airline = models.CharField(max_length=50, blank=True, null=True)

    # Kimlik / iletişim
    full_name = models.CharField(max_length=120)
    tc_no = models.CharField(
        max_length=11,
        validators=[
            MinLengthValidator(11, "TC Kimlik numarası 11 haneli olmalı."),
            RegexValidator(r"^\d{11}$", "TC Kimlik numarası sadece rakamlardan oluşmalı."),
        ],
    )
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\d{3}-\d{3}-\d{2}-\d{2}$", "Telefon formatı 5xx-xxx-xx-xx olmalı.")],
    )
    email = models.EmailField()  # yeni
    birth_date = models.DateField(null=True, blank=True)


    # Gidiş
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    travel_date = models.DateField()
    departure_time = models.TimeField(blank=True, null=True)
    flight_number = models.CharField(max_length=20, blank=True, null=True)  # yeni

    # Dönüş (opsiyonel)
    trip_type = models.CharField(max_length=20, choices=TRIP_TYPES, default="oneway")  # yeni
    return_destination = models.CharField(max_length=100, blank=True, null=True)
    return_date = models.DateField(blank=True, null=True)
    return_time = models.TimeField(blank=True, null=True)

    # Diğer
    reason_other = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    pnr_code = models.CharField(max_length=40, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Kaydı oluşturan / işleyen personel
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tickets",
    )
    purchased_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_purchased",
        help_text="Bileti alan personel",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets_rejected",
        help_text="Kaydı reddeden personel",
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
