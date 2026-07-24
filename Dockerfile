# ANNET Digital Network & NPO Operating Platform — production image.
# Multi-stage: build wheels in a full build environment, run in a slim,
# non-root final image. Gunicorn is the WSGI server; Nginx (a separate
# container — see docker-compose.yml) sits in front of it.

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


FROM python:3.11-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app && useradd --system --gid app --home /app --create-home app

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=app:app . .

RUN mkdir -p /app/staticfiles /app/media /app/private_media \
    && chown -R app:app /app/staticfiles /app/media /app/private_media \
    && chmod +x /app/docker/django/entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/accounts/login/ || exit 1

ENTRYPOINT ["/app/docker/django/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
