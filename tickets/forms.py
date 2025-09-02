# tickets/forms.py
from django import forms
from .models import TicketRequest, ChangeRequest

class TicketRequestForm(forms.ModelForm):
    class Meta:
        model = TicketRequest
        fields = [
            "user_type", "transport",
            "full_name", "tc_no", "phone",
            "origin", "destination", "travel_date",
            "return_destination", "return_date",
            "departure_time", "return_time",
            "reason", "reason_other",
            "preferred_airline",
            "notes",
        ]
        widgets = {
            "travel_date": forms.DateInput(attrs={"type": "date"}),
            "return_date": forms.DateInput(attrs={"type": "date"}),
            "departure_time": forms.TimeInput(attrs={"type": "time"}),
            "return_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        reason = cleaned.get("reason")
        reason_other = (cleaned.get("reason_other") or "").strip()

        # "Diğer" seçildiyse açıklama zorunlu
        if reason == "diger" and not reason_other:
            self.add_error("reason_other", "Lütfen 'Diğer' talep nedeni için açıklama giriniz.")

        # Sadece dönüş noktası/dönüş tarihi birlikte mantıklı olsun (ikisi de girilebilir, ikisi de boş olabilir)
        ret_dest = (cleaned.get("return_destination") or "").strip()
        ret_date = cleaned.get("return_date")

        if ret_dest and not ret_date:
            self.add_error("return_date", "Dönüş yeri seçtiyseniz dönüş tarihi de giriniz.")
        if ret_date and not ret_dest:
            self.add_error("return_destination", "Dönüş tarihi seçtiyseniz dönüş yeri de giriniz.")

        return cleaned


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ChangeRequest
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
