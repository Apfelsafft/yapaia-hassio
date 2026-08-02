# Yapaia Go als Home Assistant Add-on

> **Hinweis:** Dies ist die ursprüngliche Recherche-/Konzept-Notiz aus dem
> Hauptrepo (`Apfelsafft/Navi`, Branch `claude/ha-addon-spec`). Die
> Umsetzung selbst liegt in diesem Repo (`yapaia/`, `yapaia-routing/`) und
> weicht in Details (z. B. genaue Optionsnamen) von diesem Dokument ab —
> maßgeblich sind die `config.yaml`- und `DOCS.md`-Dateien der Add-ons.

> Recherche-Notiz (kein Code, noch nicht umgesetzt zum Zeitpunkt des
> Schreibens). Ziel: prüfen, ob und wie
> sich Yapaia Go als installierbares **Home Assistant Supervisor Add-on**
> (über den Add-on Store, "Lokale Add-ons" oder ein Custom-Repository)
> anbieten lässt — zusätzlich zum bestehenden `addons/home_assistant`-Plugin
> in diesem Repo, das nur Navigationsdaten **in** eine bestehende HA-Instanz
> pusht (REST + MQTT) und mit dieser Frage nichts zu tun hat.

---

## 0. Begriffsklärung — zwei völlig verschiedene Dinge

| Im Repo vorhanden                                   | Hier gefragt                                          |
|------------------------------------------------------|--------------------------------------------------------|
| `addons/home_assistant/` — Yapaia-internes Add-on, pusht Position/ETA per REST in eine **fremde** HA-Instanz | **Yapaia selbst** als Container im **HA Supervisor Add-on Store** installierbar machen, ähnlich wie z. B. Frigate, ESPHome oder AdGuard Home |

Diese Doku behandelt ausschließlich die zweite Frage.

**Terminologie-Hinweis:** Home Assistant hat im Februar 2026 begonnen,
"Add-on" in der UI/Doku durch **"App"** zu ersetzen (Supervisor ≥2026.02.3,
Entwickler-Doku unter `developers.home-assistant.io/docs/apps/...`). Technisch
ist es dasselbe Konzept (Docker-Container, von Supervisor verwaltet); ältere
Anleitungen und die Community sprechen weiterhin von "Add-ons". Diese Doku
nutzt "Add-on", da der Großteil der Tooling-Namen (`config.yaml`,
`repository.yaml`, Ordnerkonvention) unverändert ist.

---

## 1. Was ein HA-Add-on technisch ist

Ein Add-on ist im Kern:

1. Ein **Ordner** in einem Git-Repository mit mindestens:
   - `config.yaml` (oder `config.json`) — Metadaten + Schema
   - `Dockerfile`
   - Start-Skript (`run.sh`, meist über `s6-overlay`-Services)
2. Ein **Repository** (das Add-on-Repo selbst, oder ein größeres mit
   mehreren Add-ons), das eine `repository.yaml` im Root hat. User fügen es
   in Supervisor → Add-on Store → ⋮ → "Repositories" per Git-URL hinzu.
3. Multi-Arch-Images werden i. d. R. via `home-assistant/builder`
   GitHub-Action für `amd64/aarch64/armv7/armhf/i386` gebaut und in eine
   Registry (GHCR) gepusht; Supervisor zieht das passende Image fürs
   Zielsystem.

### Wichtige `config.yaml`-Felder für unseren Fall

| Feld | Bedeutung für Yapaia |
|------|----------------------|
| `arch` | Welche CPU-Architekturen unterstützt werden (amd64 zuerst, aarch64 für RPi 4/5) |
| `ports` / `ports_description` | z. B. `8080/tcp` für die Web-UI, falls kein Ingress |
| `ingress: true` + `ingress_port` | Eingebettetes UI **in** der HA-Sidebar, kein eigener Port nötig |
| `panel_icon`, `panel_title` | Sidebar-Eintrag |
| `map` | Welche HA-Pfade gemountet werden: `config`, `ssl`, `addons`, `backup`, `media`, `share` — **wir brauchen vor allem einen eigenen Datenbereich**, der über `/data` (automatisch von Supervisor bereitgestellt, persistent) läuft |
| `options` / `schema` | Add-on-Einstellungen, die HA-User über die UI setzen (z. B. `secret_key`, `admin_email`) — validiert gegen das Schema |
| `devices` | Für USB-GPS (`/dev/ttyUSB0`) — Add-ons können explizite Device-Mappings deklarieren, HA zeigt sie im UI als Auswahl an, falls `auto_uart: true` |
| `host_network` | Nötig falls mDNS/SSDP-Discovery gebraucht wird (für uns nicht relevant) |
| `privileged` | Nur wenn echte Hardwarezugriffe nötig sind (seriell reicht meist ohne) |
| `apparmor` | Optionales Sicherheitsprofil; Default reicht für unseren Workload |
| `backup: hot/cold/exclude` | Ob/wie der Add-on-State in HA-Backups landet |

Seit Supervisor **2026.04.0** entfällt der alte `build.yaml`-Mechanismus für
Build-Argumente — `FROM`, `LABEL`, `ARG` gehören jetzt direkt ins
`Dockerfile`, kein impliziter `BUILD_FROM`-Fallback mehr. Relevant, falls wir
uns an älteren Add-on-Tutorials orientieren.

---

## 2. Der zentrale Konflikt: Ein Container vs. unser Sieben-Container-Stack

Yapaia läuft heute als **sieben separate Docker-Services**
(`docker-compose.yml`):

```
backend · frontend (nginx) · postgres+postgis · mosquitto · graphhopper
marketplace · caddy
```

Das HA-Add-on-Modell geht implizit von **einem Container pro Add-on** aus.
Mehrere Add-ons können zwar im selben Supervisor laufen und sich per
interner DNS (`<slug>.local.hass.io`) erreichen — aber das würde bedeuten,
**sieben einzelne Add-ons** zu bauen, zu pflegen und im Store zu verwalten,
was für ein einzelnes Produkt unüblich und für Endnutzer verwirrend ist
(7 Einträge im Add-on-Store für "eine App").

**Übliche Lösung in der HA-Add-on-Welt für komplexe Apps** (siehe z. B.
Frigate, Zigbee2MQTT, Node-RED): **alles in einen Container packen**, intern
über `s6-overlay`-Services orchestriert (das ist exakt das init-System, das
die offiziellen HA-Base-Images mitbringen). Das bedeutet für uns:

| Heutiger Service | Im Add-on-Container |
|-------------------|----------------------|
| `caddy` | **entfällt** — Supervisor + HA-Frontend übernehmen TLS/Reverse-Proxy via Ingress |
| `mosquitto` | **entfällt** — Self-Hoster mit HA haben i. d. R. schon das offizielle "Mosquitto broker"-Add-on; wir sollten uns daran *anbinden* statt einen zweiten Broker zu bündeln |
| `postgres+postgis` | Entweder **mitbündeln** (eigener s6-Service, Daten unter `/data/postgres`) oder auf **SQLite** umstellen für die Add-on-Variante (deutlich leichter, aber PostGIS-Funktionen aktuell ungenutzt — zu prüfen, ob irgendwo `ST_*`-Queries existieren) |
| `graphhopper` | **mitbündeln**, größter Brocken: braucht eigenen JVM-Prozess + mehrere GB OSM-Daten + Graph-Cache unter `/data` |
| `marketplace` | mitbündeln als weiterer s6-Service, oder für die Add-on-Variante ganz weglassen (Marketplace/Add-on-System ergibt in einer bereits-gekapselten Single-Container-Welt wenig Sinn) |
| `backend` + `frontend` | Kern — bleibt, aber Frontend wird nicht mehr von nginx auf Port 8080 separat ausgeliefert, sondern vom Backend selbst oder einem internen nginx mitgeliefert, erreichbar über **Ingress** |

---

## 3. Ressourcen-Realität — der eigentliche Show-Stopper

GraphHopper für DACH-Daten braucht laut `CLAUDE.md` **`-Xmx4g`** JVM-Heap und
mehrere GB Plattenplatz für OSM-Extrakt + Graph-Cache. Viele HA-Installationen
laufen auf:

- Raspberry Pi (oft nur 2–4 GB RAM gesamt)
- Home Assistant Yellow / Green (ähnlich knapp bemessen)
- kleine NUCs mit 8 GB RAM, auf denen aber bereits HA Core + zig andere
  Add-ons laufen

Ein Yapaia-Add-on mit gebündeltem GraphHopper würde auf einem Großteil der
typischen HA-Hardware **nicht praktikabel** laufen. Realistische Optionen:

1. **"Lite"-Variante ohne eigenes Routing**: Add-on liefert nur Backend +
   Frontend + Auth + Fahrzeugprofile + Favoriten; Routing-Anfragen gehen an
   einen **extern konfigurierten** GraphHopper-Server (z. B. den, der ohnehin
   schon via `docker-compose.yml` auf einem leistungsfähigeren Mini-PC/VPS
   läuft). Das passt zum bestehenden `alt_backend_url`-Pattern aus den
   Präferenzen.
2. **"Full"-Variante mit gebündeltem GraphHopper**: nur für `amd64`/leistungsfähige
   `aarch64`-Geräte (HA-Doku erlaubt pro-Architektur-Einschränkung über
   `arch:` im Manifest), mit deutlichem RAM-Hinweis im Add-on-Description.
3. Hybrid: GraphHopper **optional** als eigenes zweites Add-on im selben
   Repository anbieten (`yapaia-routing`), das User nur installieren, wenn
   ihre Hardware es zulässt — Backend erkennt Verfügbarkeit und fällt sonst
   auf eine konfigurierbare externe Routing-URL zurück.

**Empfehlung:** Variante 1 (Lite, kein gebündeltes Routing) als primäre
Add-on-Variante. Das deckt sich auch mit dem bestehenden Self-Host-Pfad: wer
ernsthaft navigieren will, betreibt GraphHopper ohnehin auf einer dedizierten
Maschine (siehe `docs/HARDWARE.md`). Das HA-Add-on wird dann in erster Linie
für Nutzer interessant, die Yapaia **bequem aus der HA-Oberfläche heraus**
öffnen wollen (Sidebar-Tab), nicht primär für "Yapaia auf der HA-Box selbst
rechnen lassen".

---

## 4. Ingress — Yapaia-UI in der HA-Sidebar

`ingress: true` + `ingress_port: 8080` würde dazu führen, dass Supervisor das
Frontend per Reverse-Proxy einbettet und einen Sidebar-Eintrag erzeugt — ohne
eigenen offenen Port, ohne eigenes TLS-Zertifikat (HA übernimmt das).

**Wichtige Einschränkung:** HA-Ingress ersetzt **nicht automatisch** unsere
JWT-Auth. Ingress sorgt nur dafür, dass *nur eingeloggte HA-User* überhaupt
bis zum Add-on durchkommen (Schutz auf Netzwerkebene), aber es gibt keinen
Mechanismus, der automatisch eine Yapaia-Session für den HA-User erzeugt.
Praktisch bedeutet das:

- Einfachste Variante: Yapaia zeigt **innerhalb des Ingress-Frames ganz normal
  sein eigenes Login-Modal** — funktional identisch zum jetzigen Verhalten,
  nur dass man nicht mehr `https://yapaia.cloud` separat aufrufen muss.
- Fortgeschrittene Variante (deutlich mehr Aufwand, eigenes Sicherheitsrisiko):
  HA sendet bei Ingress-Requests u. a. `X-Ingress-Path` und kennt den
  anfragenden HA-User über das Supervisor-API (`/auth` Endpunkt), aber ein
  Add-on muss diese Vertrauenskette **selbst** validieren (Supervisor-Token
  prüfen, dann HA-User-Info abrufen) — das ist kein Standard-SSO, sondern
  Handarbeit, und nur sinnvoll, wenn Yapaia und HA-User wirklich 1:1
  gekoppelt sein sollen. Für ein Mehrbenutzer-Navi mit eigenem Account-Modell
  (Premium-Pläne, Admin-Rollen) ist das eher hinderlich als hilfreich.

**Empfehlung:** Ingress aktivieren für den Komfort des Sidebar-Eintrags, aber
Yapaias eigenes Auth-System unverändert beibehalten (kein SSO-Bridging).

---

## 5. Persistenz & Pfade

Supervisor stellt jedem Add-on automatisch ein beschreibbares `/data`-Verzeichnis
bereit, das Container-Neustarts und Updates überlebt. Für die Lite-Variante:

```
/data/
  postgres/         (falls Postgres mitgebündelt; sonst SQLite-Datei)
  navi.db           (SQLite-Variante)
  uploaded-addons/  (falls das interne Yapaia-Addon-System weiterhin aktiv sein soll)
```

`map: [data]` reicht für die Lite-Variante; `map: [config]`, `media`, `share`
sind für uns nicht relevant. Kein `host_network` nötig, außer für USB-GPS via
`devices:` + `auto_uart: true` (analog zum bestehenden `GPS_SERIAL_PORT`).

---

## 6. Konkreter Bauplan (für eine spätere Umsetzung)

1. Neuer Ordner im Repo (oder separates Repo) `ha-addon/yapaia/` mit:
   - `config.yaml` (slug, name, version, arch, ingress, ports, options/schema
     für `SECRET_KEY`, `BACKEND_CORS_ORIGINS`, optionale `GRAPHHOPPER_URL`)
   - `Dockerfile` FROM einem offiziellen HA-Base-Image
     (`ghcr.io/home-assistant/{arch}-base:3.x`, Alpine-basiert) +
     `s6-overlay`-Service-Definitionen für `backend` (uvicorn) und `frontend`
     (gebauter Vite-Static-Output, ausgeliefert über denselben oder einen
     schlanken internen nginx)
   - `run.sh` / s6-Services, die `SECRET_KEY` etc. aus `/data/options.json`
     lesen (Standard-Pattern: `bashio::config 'key'`)
2. `repository.yaml` im Repo-Root (oder im separaten Add-on-Repo), damit User
   es über Supervisor → Add-on Store → Repositories per Git-URL hinzufügen
   können — kein Eintrag im offiziellen HA-Add-on-Store nötig für den Start.
3. GitHub Action mit `home-assistant/builder` für Multi-Arch-Images
   (mind. `amd64`, `aarch64`; `armv7/armhf` nur falls RPi-Support gewünscht
   ist — auf Pi wird GraphHopper sowieso nicht laufen, daher für die
   Lite-Variante unproblematisch).
4. Backend-Anpassung: `GRAPHHOPPER_URL` muss bereits konfigurierbar sein
   (ist es vermutlich schon über bestehende Env-Var-Konventionen) — sonst
   kleine Änderung in `config.py`, damit die Lite-Variante auf einen
   externen Routing-Server zeigen kann, statt einen eigenen GraphHopper im
   Container zu erwarten.
5. Lokal testen über "Lokale Add-ons" (Supervisor erkennt Ordner unter
   `/addons/local/` auf dem HA-Host) bevor man ein eigenes Add-on-Repository
   veröffentlicht.

---

## 7. Empfehlung / Fazit

- **Realistisch und sinnvoll:** Eine **schlanke** Yapaia-Add-on-Variante
  (Backend + Frontend + SQLite, kein gebündeltes GraphHopper/Postgres/MQTT/
  Caddy), die sich gegen einen extern laufenden Yapaia-Routing-Stack
  verbindet — primär als bequemer Sidebar-Zugang für Leute, die Yapaia schon
  auf einem VPS/Mini-PC betreiben und es zusätzlich aus ihrer HA-Oberfläche
  öffnen wollen.
- **Nicht empfehlenswert (zumindest nicht als Erstschritt):** Den gesamten
  Sieben-Container-Stack 1:1 in ein einzelnes Add-on zu pressen. Hoher
  Wartungsaufwand, schlechte HA-Hardware-Kompatibilität (RAM/Disk durch
  GraphHopper), und es widerspricht dem Ein-Container-Idiom des
  Add-on-Ökosystems.
- **Kein Aufwand, sofort nutzbar:** Das bereits vorhandene
  `addons/home_assistant`-Plugin (Yapaia → HA-Sensoren) bleibt die richtige
  Antwort für "Navigationsdaten in HA sichtbar machen". Das hier beschriebene
  Add-on ist die *umgekehrte* Richtung ("HA-Sidebar → Yapaia-UI") und ein
  unabhängiges, optionales Zusatzprojekt.

**Nächster Schritt, falls gewünscht:** Abschnitt 6 als Umsetzungs-Spec in
`PLANNING.md` übernehmen (analog zum DATEX-II-Eintrag), sobald die Lite- vs.
Full-Entscheidung getroffen ist.

---

## 8. Umsetzungs-Spec: Zwei-Add-on-Struktur

> Konkrete, ausführbare Anleitung für die Aufteilung in zwei kooperierende
> Add-ons in einem gemeinsamen Add-on-Repository. Geschrieben so, dass eine
> CLI-Session das Ganze ohne weitere Rückfragen umsetzen kann.

### 8.1 Repository-Layout

Eigenes neues GitHub-Repo (oder dieses Repo mit Add-on-Ordnern im Root —
HA Supervisor erlaubt beides; **separates Repo empfohlen**, damit User
`Apfelsafft/Navi` nicht klonen müssen, nur um das Add-on zu installieren).

Vorschlag: **neues Repo `Apfelsafft/yapaia-hassio`** mit:

```
yapaia-hassio/
├── repository.yaml          # Pflicht für HA-Add-on-Repos
├── README.md
├── yapaia/                  # Add-on 1: UI + Backend + SQLite
│   ├── config.yaml
│   ├── Dockerfile
│   ├── rootfs/              # s6-overlay services
│   │   └── etc/services.d/
│   │       ├── backend/run
│   │       └── nginx/run
│   ├── icon.png             # 256×256
│   ├── logo.png             # 250×100, transparent
│   └── DOCS.md
└── yapaia-routing/          # Add-on 2: GraphHopper
    ├── config.yaml
    ├── Dockerfile
    ├── rootfs/etc/services.d/graphhopper/run
    ├── icon.png
    ├── logo.png
    └── DOCS.md
```

`repository.yaml`:

```yaml
name: Yapaia Go
url: https://github.com/Apfelsafft/yapaia-hassio
maintainer: Apfelsafft <apfelsafft@gmail.com>
```

### 8.2 Add-on 1: `yapaia` (Kern)

#### `yapaia/config.yaml`

```yaml
name: Yapaia Go
version: "0.5.0"
slug: yapaia
description: Browserbasiertes Turn-by-Turn-Navi mit Add-on-System, läuft komplett lokal.
url: https://github.com/Apfelsafft/yapaia-hassio
arch:
  - amd64
  - aarch64
init: false
startup: application
boot: auto
hassio_api: false                # nicht benötigt
homeassistant_api: false         # wir reden nicht zurück ins HA Core
ingress: true
ingress_port: 8080
panel_icon: mdi:navigation-variant
panel_title: Yapaia Navi
host_network: false
map:
  - "data:rw"
ports:
  8080/tcp: null                 # null = nur über Ingress, kein externer Port
ports_description:
  8080/tcp: Web-UI (nur falls direkter Zugriff ohne Ingress gewünscht)
devices: []                      # USB-GPS wird via udev_rules zur Laufzeit konfiguriert, siehe 8.5
udev: true                       # erlaubt USB-Device-Auswahl im HA-UI
services:
  - mqtt:want                    # bindet sich automatisch ans Mosquitto-Addon falls vorhanden
discovery: []
options:
  secret_key: ""
  admin_emails: ""
  graphhopper_url: "http://a0d7b954-yapaia-routing:8989"
  photon_url: ""
  google_client_id: ""
  google_client_secret: ""
  gps_serial_port: ""
  gps_serial_baud: 9600
  log_level: info
schema:
  secret_key: "password?"
  admin_emails: "str?"
  graphhopper_url: "url?"
  photon_url: "url?"
  google_client_id: "str?"
  google_client_secret: "password?"
  gps_serial_port: "str?"
  gps_serial_baud: "int(1200,115200)"
  log_level: "list(debug|info|warning|error)"
backup: hot
backup_exclude:
  - "*.tmp"
  - "graphhopper-cache/**"       # wird vom anderen Add-on verwaltet
image: ghcr.io/apfelsafft/yapaia-hassio/{arch}-yapaia
```

**Hinweise zu den Feldern:**

- `secret_key: "password?"` — `?` = optional; wenn leer, generiert das
  Start-Skript einen mit `openssl rand -hex 32` und schreibt ihn nach
  `/data/secret_key` (persistent über Updates).
- `graphhopper_url` Default zeigt auf den Hostnamen des Routing-Add-ons.
  **Supervisor-DNS-Schema:** `<repo-slug>-<addon-slug>`, gepunkteter Prefix
  variiert je nach Repo (für Custom-Repos: SHA-Prefix des Repos). Sicherer
  Default: leer lassen, im Setup-Step prompten. Alternativ: das User-UI im
  Add-on bietet einen "Routing-Server auto-discovern"-Button (Probe-Request
  auf gängige Add-on-Hostnamen).
- `services: ["mqtt:want"]` — `want` = wenn das offizielle Mosquitto-Add-on
  läuft, bekommt Yapaia automatisch `MQTT_HOST`/`MQTT_USERNAME`/`MQTT_PASSWORD`
  als Env-Vars injiziert (Discovery-API von Supervisor).
- `udev: true` macht USB-GPS-Auswahl im UI verfügbar; tatsächlicher
  Device-Mount geschieht zur Laufzeit über `devices` im UI durch den User
  (HA-Standard-Flow für serielle Geräte).
- `backup: hot` — Add-on wird im Backup mitgesichert, ohne dass es gestoppt
  werden muss; SQLite verträgt das wenn WAL aktiv ist.

#### `yapaia/Dockerfile`

```dockerfile
ARG BUILD_FROM
# In CI ersetzt der HA-Builder BUILD_FROM durch ghcr.io/home-assistant/{arch}-base-python:3.12-alpine3.20
FROM $BUILD_FROM

ENV LANG=C.UTF-8

# System-Pakete: nginx für Frontend-Static-Serving, postgresql-client raus (SQLite),
# tini ist im base-image schon vorhanden.
RUN apk add --no-cache nginx nodejs npm git build-base python3-dev

WORKDIR /opt/yapaia

# 1. Backend kopieren + installieren
COPY backend/ ./backend/
RUN cd backend && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir aiosqlite

# 2. Frontend bauen
COPY frontend/ ./frontend/
RUN cd frontend && npm ci && npm run build \
    && mv dist /opt/yapaia/frontend-dist \
    && rm -rf node_modules

# 3. Bundled Add-ons (mit-shippen, ohne marketplace)
COPY addons/ ./addons/

# 4. nginx-Config für /api → backend:8000, alles andere → static
COPY rootfs/etc/nginx/http.d/default.conf /etc/nginx/http.d/default.conf

# 5. s6-overlay services (init=true ist im base-image bereits aktiv)
COPY rootfs/etc/services.d/ /etc/services.d/

LABEL \
  io.hass.version="0.5.0" \
  io.hass.type="addon" \
  io.hass.arch="amd64|aarch64"
```

**Wichtig (Supervisor 2026.04.0+):** Kein `build.yaml` mehr. `BUILD_FROM` wird
nur dann sauber ersetzt, wenn die GitHub-Action `home-assistant/builder` mit
`--target yapaia` aufgerufen wird; siehe 8.4.

#### `yapaia/rootfs/etc/services.d/backend/run`

```bash
#!/usr/bin/with-contenv bashio
set -e

# Optionen aus HA-UI lesen
SECRET_KEY=$(bashio::config 'secret_key')
ADMIN_EMAILS=$(bashio::config 'admin_emails')
GRAPHHOPPER_URL=$(bashio::config 'graphhopper_url')
PHOTON_URL=$(bashio::config 'photon_url')
GOOGLE_CLIENT_ID=$(bashio::config 'google_client_id')
GOOGLE_CLIENT_SECRET=$(bashio::config 'google_client_secret')
GPS_SERIAL_PORT=$(bashio::config 'gps_serial_port')
GPS_SERIAL_BAUD=$(bashio::config 'gps_serial_baud')

# Bei leerem secret_key: einmalig generieren + persistieren
if [ -z "$SECRET_KEY" ]; then
  if [ ! -f /data/secret_key ]; then
    openssl rand -hex 32 > /data/secret_key
    bashio::log.warning "Auto-generated SECRET_KEY at /data/secret_key"
  fi
  SECRET_KEY=$(cat /data/secret_key)
fi

# MQTT-Credentials aus Services-API holen (falls Mosquitto-Addon läuft)
if bashio::services.available "mqtt"; then
  MQTT_HOST=$(bashio::services mqtt "host")
  MQTT_PORT=$(bashio::services mqtt "port")
  MQTT_USERNAME=$(bashio::services mqtt "username")
  MQTT_PASSWORD=$(bashio::services mqtt "password")
  export MQTT_HOST MQTT_PORT MQTT_USERNAME MQTT_PASSWORD
fi

export SECRET_KEY ADMIN_EMAILS
export GRAPHHOPPER_URL PHOTON_URL
export GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
export GPS_SERIAL_PORT GPS_SERIAL_BAUD

# Yapaia-spezifisch: SQLite statt Postgres
export DATABASE_URL="sqlite+aiosqlite:////data/yapaia.db"
export BACKEND_CORS_ORIGINS="*"   # Ingress proxied, externe Origins egal

# Bundled Marketplace deaktivieren — im Add-on-Kontext nicht sinnvoll
export MARKETPLACE_URL=""

cd /opt/yapaia/backend
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

#### `yapaia/rootfs/etc/services.d/nginx/run`

```bash
#!/usr/bin/with-contenv bashio
exec nginx -g "daemon off;"
```

#### `yapaia/rootfs/etc/nginx/http.d/default.conf`

```nginx
server {
    listen 8080 default_server;
    root /opt/yapaia/frontend-dist;
    index index.html;

    # Ingress: HA setzt X-Ingress-Path; das ist der Base-Path im iframe.
    # Vite-Build muss mit base="./" gebaut werden, damit assets relativ aufgelöst werden.

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 8.3 Add-on 2: `yapaia-routing` (GraphHopper)

#### `yapaia-routing/config.yaml`

```yaml
name: Yapaia Routing (GraphHopper)
version: "0.5.0"
slug: yapaia_routing
description: GraphHopper-Routing-Engine für Yapaia. Benötigt ≥6 GB RAM und ≥20 GB freien Plattenplatz für DACH-Datensatz.
url: https://github.com/Apfelsafft/yapaia-hassio
arch:
  - amd64
  - aarch64
init: false
startup: services
boot: auto
hassio_api: false
ingress: false                   # rein interner Service, keine UI
host_network: false
map:
  - "data:rw"
ports:
  8989/tcp: 8989                 # exponiert für andere Add-ons UND optional direkten Zugriff
ports_description:
  8989/tcp: GraphHopper HTTP-API (nur in lokalem Netz freigeben)
options:
  region: "germany"
  pbf_url: "https://download.geofabrik.de/europe/germany-latest.osm.pbf"
  java_heap_gb: 4
  reimport_on_startup: false
schema:
  region: "list(germany|dach|europe|custom)"
  pbf_url: "url"
  java_heap_gb: "int(2,16)"
  reimport_on_startup: "bool"
backup: cold                     # GraphHopper-Cache zu groß für Hot-Backup
backup_exclude:
  - "graph-cache/**"
  - "*.osm.pbf"
image: ghcr.io/apfelsafft/yapaia-hassio/{arch}-yapaia-routing
```

#### `yapaia-routing/Dockerfile`

```dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8

RUN apk add --no-cache openjdk21-jre wget bash

ARG GRAPHHOPPER_VERSION=8.0
RUN mkdir -p /opt/graphhopper && cd /opt/graphhopper && \
    wget -O graphhopper.jar \
    https://github.com/graphhopper/graphhopper/releases/download/${GRAPHHOPPER_VERSION}/graphhopper-web-${GRAPHHOPPER_VERSION}.jar

COPY config.yml /opt/graphhopper/config.yml
COPY rootfs/etc/services.d/ /etc/services.d/

LABEL \
  io.hass.version="0.5.0" \
  io.hass.type="addon" \
  io.hass.arch="amd64|aarch64"
```

`config.yml` ist eine 1:1-Kopie aus `infra/graphhopper/config.yml` (die
Custom-Models bleiben unverändert; `weighting: custom` + `custom_model_files: []`
für alle Profile).

#### `yapaia-routing/rootfs/etc/services.d/graphhopper/run`

```bash
#!/usr/bin/with-contenv bashio
set -e

REGION=$(bashio::config 'region')
PBF_URL=$(bashio::config 'pbf_url')
HEAP_GB=$(bashio::config 'java_heap_gb')
REIMPORT=$(bashio::config 'reimport_on_startup')

PBF_FILE="/data/${REGION}.osm.pbf"
CACHE_DIR="/data/graph-cache"

# OSM-Datei laden, falls nicht vorhanden
if [ ! -f "$PBF_FILE" ]; then
  bashio::log.info "Downloading OSM extract for ${REGION} ..."
  wget -q -O "$PBF_FILE" "$PBF_URL" || bashio::exit.nok "Download failed"
fi

# Reimport erzwingen falls gewünscht
if [ "$REIMPORT" = "true" ] && [ -d "$CACHE_DIR" ]; then
  bashio::log.warning "Reimport requested — wiping graph-cache"
  rm -rf "$CACHE_DIR"
fi

cd /opt/graphhopper
exec java \
  -Xmx${HEAP_GB}g -Xms1g \
  -Ddw.graphhopper.datareader.file="$PBF_FILE" \
  -Ddw.graphhopper.graph.location="$CACHE_DIR" \
  -jar graphhopper.jar server config.yml
```

### 8.4 CI / Build-Pipeline

GitHub-Action `.github/workflows/builder.yml` im Add-on-Repo:

```yaml
name: Build Add-ons
on:
  push:
    branches: [main]
    tags: ['v*']
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        addon: [yapaia, yapaia-routing]
        arch: [amd64, aarch64]
    steps:
      - uses: actions/checkout@v4
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build & push
        uses: home-assistant/builder@2025.03.0
        with:
          args: |
            --${{ matrix.arch }} \
            --target ${{ matrix.addon }} \
            --image ghcr.io/apfelsafft/yapaia-hassio/{arch}-${{ matrix.addon }} \
            --docker-hub ghcr.io \
            --addon
```

### 8.5 Backend-Änderungen am Yapaia-Hauptrepo

Damit das Backend in der SQLite-Variante läuft:

1. **`backend/app/db.py`** — `DATABASE_URL` aus Env-Var lesen statt zusammenbauen:
   ```python
   DATABASE_URL = os.environ.get("DATABASE_URL") or (
       f"postgresql+asyncpg://{settings.postgres_user}:..."
   )
   engine = create_async_engine(DATABASE_URL, echo=False, connect_args=(
       {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
   ))
   ```
2. **Migrationen Postgres-spezifisch entzuckern.** Aktuelle Statements
   verwenden `TIMESTAMPTZ`, `NOW()`, `ALTER COLUMN … SET DEFAULT NOW()`,
   `BOOLEAN` — SQLite akzeptiert das meiste duck-typed, aber:
   - `NOW()` → durch SQLAlchemy `server_default=func.current_timestamp()` ersetzen
   - `TIMESTAMPTZ` → `DateTime(timezone=True)` (SQLAlchemy macht das richtig auf beiden Engines)
   - `ALTER COLUMN ... SET DEFAULT` → SQLite kann das nicht; Statement in einen Postgres-only-Branch verschieben:
     ```python
     if engine.dialect.name == "postgresql":
         await conn.execute(text("ALTER TABLE user_addons ALTER COLUMN installed_at SET DEFAULT NOW()"))
     ```
   - `UNIQUE`-Constraints nachträglich → SQLite braucht stattdessen einen
     expliziten `CREATE UNIQUE INDEX IF NOT EXISTS`.
3. **Marketplace-Calls absichern.** `backend/app/api/addons.py` macht
   `httpx.get(settings.marketplace_url)`. In der Add-on-Variante ist
   `MARKETPLACE_URL=""`, Code muss das früh als "Marketplace deaktiviert"
   behandeln (HTTP 503 mit klarer Meldung) statt 500 bei `connect refused`.
4. **Frontend-Build mit relativer Base.** `frontend/vite.config.ts` muss
   `base: "./"` setzen (oder dynamisch `base: process.env.YAPAIA_HA_INGRESS ? "./" : "/"`)
   — sonst lädt der eingebettete Ingress-Frame keine Assets, weil HA den Frame
   unter `/api/hassio_ingress/<token>/` mountet.
5. **WebSocket-URL im Frontend.** `navSocket.ts` baut aktuell `ws://…/ws/...`
   relativ aus `VITE_BACKEND_URL`. Im Ingress-Kontext muss das auf
   `wss://${location.host}${ingressBasePath}/ws/...` mappen — am
   einfachsten via `window.location` + dem von HA gelieferten Base-Path
   (verfügbar als URL-Prefix im aktuellen Pfad).

Diese 5 Änderungen sind **Repository-übergreifend**: sie passieren im
`Navi`-Hauptrepo (nicht im Add-on-Repo), damit das normale Self-Host-Setup
unverändert weiterläuft. Empfohlene Branch-Strategie:
ein PR `feat/ha-addon-compat` im Hauptrepo + ein initialer Commit im
`yapaia-hassio`-Repo, beide gemeinsam getestet.

### 8.6 Test-Plan

1. **Lokales Add-on:** Code in `/addons/local/yapaia/` auf einem
   HA-OS-Test-System ablegen. Supervisor → Add-on Store → ⋮ → "Lokale
   Add-ons neu laden". Beide Add-ons sollten erscheinen.
2. **Routing-Add-on zuerst starten,** OSM-Download abwarten
   (Germany ~4 GB, Import ~30 min auf NUC-Klasse-Hardware).
3. **Kern-Add-on starten,** Ingress-Tab in Sidebar öffnen.
4. **Smoke-Tests:**
   - Registrierung neuer User, Login funktioniert
   - Adresssuche liefert Treffer (Nominatim-Fallback, da Photon nicht
     gebündelt)
   - Route Berlin → München berechnet sich
   - GPS-Simulator startet
5. **Backup/Restore-Test:** HA-Full-Backup, anschließend Add-on löschen +
   neu installieren, Backup einspielen → User + Fahrzeuge + Favoriten
   sollten erhalten sein (SQLite-Datei aus `/data` wird mit-gesichert).
6. **Multi-Arch:** Image auf `aarch64` (RPi 5 oder OrangePi) testen, da
   GitHub-Builder gerne mal arch-spezifische Issues hat.

### 8.7 Out of Scope für die erste Iteration

- Photon-Geocoding bündeln (ist optional in Yapaia, Nominatim-Fallback reicht)
- HA-User → Yapaia-User-Mapping/SSO (siehe Abschnitt 4 — bewusst nicht jetzt)
- Eintrag in den offiziellen HA-Add-on-Store (erst nach 1–2 Releases via
  Custom-Repository stabilisieren)
- Tile-Server bündeln (PMTiles-Datei ist im Frontend-Bundle als URL
  konfigurierbar; für Add-on-Variante: externe Tile-URL in Options
  ergänzen, falls offline-Tiles gewünscht)

---

## Quellen

- [App configuration — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/apps/configuration/)
- [Presenting your app — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/apps/presentation/)
- [home-assistant/supervisor Release 2026.04.0](https://github.com/home-assistant/supervisor/releases/tag/2026.04.0)
- [home-assistant/supervisor Release 2026.02.3](https://github.com/home-assistant/supervisor/releases/tag/2026.02.3)
- [Rename "Add-ons" to "Apps" — home-assistant/architecture Discussion #1287](https://github.com/home-assistant/architecture/discussions/1287)
