ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies:
# - nginx: static frontend + reverse proxy for /api and /ws
# - nodejs/npm: build the Vite frontend at image-build time
# - build-base/python3-dev: required by some Python wheels (bcrypt, lxml)
# - openssl: secret_key generation in run script
RUN apk add --no-cache \
        nginx \
        nodejs \
        npm \
        build-base \
        python3-dev \
        libffi-dev \
        openssl \
        bash

WORKDIR /opt/yapaia

# 1. Backend source + dependencies (incl. aiosqlite for SQLite mode)
COPY backend/ ./backend/
RUN cd backend && pip install --no-cache-dir . \
    && pip install --no-cache-dir aiosqlite

# 2. Bundled Yapaia add-ons (track_recorder, camera, mapstyle, …)
COPY addons/ ./addons/

# 3. Frontend build — Vite with base="./" so assets resolve under Ingress
COPY frontend/ ./frontend/
RUN cd frontend && \
    npm ci --no-audit --no-fund && \
    YAPAIA_HA_INGRESS=1 npm run build && \
    mv dist /opt/yapaia/frontend-dist && \
    rm -rf node_modules

# 4. nginx + s6 services
COPY rootfs/ /

# Clean up build-only deps to slim the final image
RUN apk del --no-cache nodejs npm build-base python3-dev libffi-dev

EXPOSE 8080

LABEL \
    io.hass.name="Yapaia Go" \
    io.hass.description="Browser-based turn-by-turn navigation" \
    io.hass.version="0.5.0" \
    io.hass.type="addon" \
    io.hass.arch="amd64|aarch64" \
    maintainer="Apfelsafft <apfelsafft@gmail.com>"
