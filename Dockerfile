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

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN chmod +x /app/deploy/entrypoint-web.sh /app/deploy/entrypoint-worker.sh \
    && uv sync --frozen --no-dev \
    && uv run python manage.py tailwind download_cli \
    && uv run python manage.py tailwind build

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["/app/deploy/entrypoint-web.sh"]
