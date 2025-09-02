# t3ticket/settings.py
from pathlib import Path
import os
import warnings
import dj_database_url
# -----------------------------
# Proje yolu + .env
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

# -----------------------------
# Güvenlik / temel
# -----------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# -----------------------------
# Google Sheets yapılandırması
# (Service Account önerilir)
# -----------------------------
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")   # örn: C:\...\gsa.json
GOOGLE_SERVICE_ACCOUNT_INFO = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO", "")
GOOGLE_SERVICE_ACCOUNT_INFO_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO_B64", "")# JSON string (opsiyonel)

SHEETS_TICKETS_WORKSHEET = os.getenv("SHEETS_TICKETS_WORKSHEET", "Tickets")
SHEETS_CHANGES_WORKSHEET = os.getenv("SHEETS_CHANGES_WORKSHEET", "Changes")

# (Opsiyonel) Eski Apps Script köprüsü — boş bırakılabilir
SHEETS_WEBAPP_URL = os.getenv("SHEETS_WEBAPP_URL", "")
SHEETS_WEBAPP_TOKEN = os.getenv("SHEETS_WEBAPP_TOKEN", "")
SHEETS_WEBAPP_TIMEOUT = float(os.getenv("SHEETS_WEBAPP_TIMEOUT", "15"))

if not GOOGLE_SHEETS_SPREADSHEET_ID:
    warnings.warn("⚠️ GOOGLE_SHEETS_SPREADSHEET_ID boş. Google Sheets senkronu çalışmayacaktır.")

# -----------------------------
# Django apps
# -----------------------------
ENABLE_JAZZMIN = os.getenv("ENABLE_JAZZMIN", "true").lower() == "true"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tickets",
]
if ENABLE_JAZZMIN:
    INSTALLED_APPS.insert(0, "jazzmin")  # pip kurulumu yoksa ENABLE_JAZZMIN=false yap

# (opsiyonel) Jazzmin görünüm ayarları
JAZZMIN_SETTINGS = {
    "site_title": "Bilet Yönetimi",
    "site_header": "T3 Bilet Yönetimi",
    "site_brand": "T3 Bilet",
    "welcome_sign": "T3 Bilet Yönetim Paneli",
    "show_ui_builder": False,
    "changeform_format": "vertical_tabs",
    "topmenu_links": [
        {"name": "Personel Paneli", "url": "/panel/"},
        {"name": "Durum Sorgu", "url": "/durum/"},
    ],
}

# -----------------------------
# Middleware
# -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------------------
# URLs / Templates
# -----------------------------
ROOT_URLCONF = "t3ticket.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "t3ticket.wsgi.application"

# -----------------------------
# Veritabanı
# -----------------------------
DATABASES = {
    'default': dj_database_url.config(
        default="postgresql://t3ticket_db_user:rVVf6VyWtaPCgQpsrTdmmDBc7t2Pehwz@dpg-d2red2mr433s73fi2l3g-a.oregon-postgres.render.com/t3ticket_db",
        conn_max_age=600,
        ssl_require=True
    )
}

# -----------------------------
# Parola validasyonları
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------
# Yerelleştirme
# -----------------------------
LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# -----------------------------
# Statik dosyalar
# -----------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------
# Giriş/Çıkış yönlendirmeleri
# -----------------------------
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/panel/"
LOGOUT_REDIRECT_URL = "/"

# -----------------------------
# Logging (konsol + dosya)
# -----------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "class": "logging.FileHandler",
            "filename": str(BASE_DIR / "runtime.log"),
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "": {"handlers": ["console", "file"], "level": "WARNING"},
        "tickets": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
    },
}
