#!/bin/bash
set -e  # hata olursa scripti durdurur

# Gereksinimleri yükle
pip install -r requirements.txt

# Migrasyonları uygula
python manage.py migrate

# Statik dosyaları topla
python manage.py collectstatic --noinput

# Superuser oluştur (varsa hata vermesin diye || true ekleniyor)
DJANGO_SUPERUSER_USERNAME=admin \
DJANGO_SUPERUSER_PASSWORD=admin123 \
DJANGO_SUPERUSER_EMAIL=admin@example.com \
python manage.py createsuperuser --noinput || true
