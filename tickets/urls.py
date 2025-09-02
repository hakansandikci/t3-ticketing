from django.contrib import admin
from django.urls import path
from django.contrib.auth.decorators import user_passes_test
from . import views

def superuser_only(user):
    from django.conf import settings
    return (getattr(settings, "ADMIN_ONLY_SUPERUSER", False) is False) or user.is_superuser

app_name = "tickets"

admin.site.login = user_passes_test(superuser_only)(admin.site.login)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("talep-yeni/", views.request_create, name="request_create"),
    path("durum/", views.request_status_lookup, name="status_lookup"),
    path("durum/<str:tracking_code>/", views.request_status_detail, name="status_detail"),
    # staff
    path("panel/", views.staff_dashboard, name="staff_dashboard"),
    path("panel/ticket/<int:pk>/", views.staff_ticket_edit, name="staff_ticket_edit"),
    path("panel/export/csv/", views.export_csv, name="export_csv"),
    path("panel/export/xlsx/", views.export_xlsx, name="export_xlsx"),
    path("panel/reports/", views.reports, name="reports"),
    
]
