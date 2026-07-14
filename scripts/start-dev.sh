#!/usr/bin/env bash
set -Eeuo pipefail

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
exec python manage.py runserver 0.0.0.0:8000
