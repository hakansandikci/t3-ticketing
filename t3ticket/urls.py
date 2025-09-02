from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Uygulama URL'leri
    path("", include("tickets.urls")),
    path("admin/", admin.site.urls),   # ✅ Django admin


    # Ana sayfaya yönlendirme
    path("", RedirectView.as_view(pattern_name="tickets:home", permanent=False)),

    # Kimlik doğrulama
    path("accounts/", include("django.contrib.auth.urls")),
]
