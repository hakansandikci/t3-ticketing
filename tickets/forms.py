from django import forms
from .models import TicketRequest, ChangeRequest, Option

class TicketRequestForm(forms.ModelForm):
    class Meta:
        model = TicketRequest
        fields = [
            "trip_type",
            "user_type",
            "full_name",
            "email",
            "birth_date",
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
            "preferred_airline",   # ✅ EKLENDİ
            "flight_number",
            "transport",
            "notes",               # ✅ EKLENDİ
        ]


        widgets = {
            "trip_type": forms.RadioSelect,
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "phone": forms.TextInput(attrs={"placeholder": "5xx-xxx-xx-xx"}),
            "travel_date": forms.DateInput(attrs={"type": "date"}),
            "return_date": forms.DateInput(attrs={"type": "date"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
            "return_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Admin’de eklenen Option kayıtlarını dinamik olarak forma bağla
        self.fields["user_type"].widget = forms.Select(
            choices=[(o.value, o.value) for o in Option.objects.filter(category="user_type")]
        )
        self.fields["transport"].widget = forms.Select(
            choices=[(o.value, o.value) for o in Option.objects.filter(category="transport")]
        )
        self.fields["reason"].widget = forms.Select(
            choices=[(o.value, o.value) for o in Option.objects.filter(category="reason")]
        )
        self.fields["preferred_airline"].widget = forms.Select(
            choices=[("", "—")] + [(o.value, o.value) for o in Option.objects.filter(category="airline")]
        )

    def clean(self):
        cleaned = super().clean()

        # Diğer neden seçilmişse açıklama zorunlu
        reason = cleaned.get("reason")
        reason_other = (cleaned.get("reason_other") or "").strip()
        if reason == "Diğer" and not reason_other:
            self.add_error("reason_other", "Lütfen 'Diğer' talep nedeni için açıklama giriniz.")

        # Gidiş–Dönüş seçildiyse dönüş bilgileri zorunlu
        if cleaned.get("trip_type") == "roundtrip":
            if not cleaned.get("return_destination"):
                self.add_error("return_destination", "Gidiş–Dönüş için dönüş yeri zorunludur.")
            if not cleaned.get("return_date"):
                self.add_error("return_date", "Gidiş–Dönüş için dönüş tarihi zorunludur.")
            if not cleaned.get("return_time"):
                self.add_error("return_time", "Gidiş–Dönüş için dönüş saati zorunludur.")

        return cleaned


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ChangeRequest
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
