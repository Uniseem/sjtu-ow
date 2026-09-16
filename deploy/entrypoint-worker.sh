#!/bin/sh
set -eu

mkdir -p /app/data /app/media /app/prerendered
exec python manage.py run_worker
