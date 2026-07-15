FROM node:24.18.0-bookworm-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY assets ./assets
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.13-slim-bookworm AS builder

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    build-essential \
    pkg-config \
    libpq-dev \
    libmariadb-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --python 3.13

FROM python:3.13-slim-bookworm AS runtime

RUN apt-get update --yes --quiet && apt-get install --yes --quiet --no-install-recommends \
    libpq5 \
    libmariadb3 \
    libjpeg62-turbo \
    libwebp7 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd wagtail

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

RUN mkdir -p /app/media /app/staticfiles \
 && chown -R wagtail:wagtail /app

COPY --chown=wagtail:wagtail . .
COPY --from=frontend --chown=wagtail:wagtail /app/app/static/css/app.css /app/app/static/css/app.css
COPY --from=frontend --chown=wagtail:wagtail /app/app/static/js/app.js /app/app/static/js/app.js

USER wagtail

CMD ["gunicorn", "app.wsgi:application"]
