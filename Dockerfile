FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod \
    DJANGO_SECRET_KEY=build-time-only \
    FIELD_ENCRYPTION_KEY=build-time-only \
    DJANGO_ALLOWED_HOSTS=localhost \
    DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost \
    SITE_URL=http://localhost \
    DJANGO_SECURE_SSL_REDIRECT=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g libwebp7 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv

# The Tailwind CLI (112 MB) in its own layer before the code: a code change
# no longer downloads it again, and a GitHub hiccup only hurts the first build
# (round 144). Keep in step with TAILWIND_CLI_VERSION in settings/base.py.
ARG TAILWIND_CLI_VERSION=2.9.0
COPY deploy/fetch_tailwind_cli.py /tmp/fetch_tailwind_cli.py
RUN python /tmp/fetch_tailwind_cli.py "$TAILWIND_CLI_VERSION" /app/.django_tailwind_cli

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN chmod +x /app/deploy/entrypoint-web.sh /app/deploy/entrypoint-worker.sh \
    && uv sync --frozen --no-dev \
    && uv run python manage.py tailwind build

ENV PATH="/app/.venv/bin:$PATH"

# Not root (216, C10): the processes run as "app". The volumes' mount points
# are made here and owned by it, so a new volume starts out writable; volumes
# made before 216 belong to root and are handed over once when upgrading
# (README「升级」). `docker compose exec` runs as this user too, so files the
# cron jobs write (backups, the database's -wal) stay the app's.
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /app/data /app/media /app/staticfiles /app/prerendered /app/backups \
    && chown app:app /app/data /app/media /app/staticfiles /app/prerendered /app/backups
USER app

EXPOSE 8000

CMD ["/app/deploy/entrypoint-web.sh"]
