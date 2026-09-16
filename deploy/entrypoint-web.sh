#!/bin/sh
set -eu

mkdir -p /app/data /app/media /app/staticfiles /app/prerendered

# Idempotent. Keeps existing hashed files on the static volume (no --clear).
python manage.py createcachetable
python manage.py collectstatic --noinput

exec gunicorn sjtu_ow.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile -
