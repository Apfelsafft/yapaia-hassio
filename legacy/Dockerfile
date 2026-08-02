ARG BUILD_FROM
FROM $BUILD_FROM

# Node.js für Frontend-Build
RUN apk add --no-cache nodejs npm curl

WORKDIR /app

# Frontend bauen
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm ci
COPY frontend ./frontend
RUN cd frontend && npm run build

# Python-Backend installieren
COPY backend/pyproject.toml ./backend/
RUN pip install --break-system-packages -e ./backend/
COPY backend ./backend

# Gebautes Frontend als statische Dateien ins Backend legen
# → FastAPI serviert es unter / wenn backend/static/ existiert
RUN cp -r frontend/dist backend/static

COPY ha-addon/run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8000
CMD ["/run.sh"]
