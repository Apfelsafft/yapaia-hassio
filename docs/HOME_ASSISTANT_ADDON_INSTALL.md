# Yapaia Go als Home Assistant Add-on — Installationsanleitung

End-to-End-Anleitung für die Installation der zwei Yapaia-HA-Add-ons auf
einem Home Assistant OS / Supervised System.

> **Voraussetzung:** Home Assistant Operating System oder Home Assistant
> Supervised. Auf "Home Assistant Container" (nacktes Docker) **funktioniert
> das nicht** — Supervisor ist Pflicht, da nur dieser die Add-on-Verwaltung
> bereitstellt.

---

## 1. Übersicht — was wird installiert?

| Add-on | Wofür | RAM | Disk |
|--------|-------|-----|------|
| **Yapaia Go** (`yapaia`) | UI + Backend + SQLite, eingebettet in HA-Sidebar | ~300 MB | ~200 MB |
| **Yapaia Routing** (`yapaia_routing`) | GraphHopper-Routing-Engine (optional) | ~5 GB | ~20 GB inkl. OSM |

**Beide installieren** wenn Yapaia komplett lokal auf der HA-Box laufen soll.

**Nur `yapaia` installieren** wenn bereits ein GraphHopper auf einem
anderen Server (z. B. dem klassischen Yapaia-VPS-Stack) läuft. In dem Fall
trägt man die externe URL in den Add-on-Optionen ein.

---

## 2. Hardware-Check

Vor der Installation kurz prüfen:

```bash
# Auf dem HA-Host (z.B. via Terminal-Add-on oder SSH)
free -h          # Verfügbares RAM
df -h /data      # Freier Plattenplatz auf /data (oder /usr/share/hassio)
```

**Mindestanforderungen für die Komplettinstallation (beide Add-ons):**

- 8 GB RAM (mindestens 6 GB frei)
- 30 GB freier Plattenplatz
- amd64 oder aarch64 CPU

Auf Raspberry Pi 4 (4 GB) / HA Yellow / HA Green: **nur das `yapaia`-Add-on**
installieren und externe Routing-URL verwenden.

---

## 3. Add-on-Repository hinzufügen

1. Home Assistant öffnen
2. **Einstellungen** → **Add-ons** → **Add-on-Store**
3. Rechts oben **⋮** → **Repositories**
4. Diese URL eintragen:
   ```
   https://github.com/Apfelsafft/yapaia-hassio
   ```
5. **Hinzufügen** → kurz warten

---

## 4. Add-on 2 zuerst: `Yapaia Routing` installieren (optional)

> Reihenfolge: zuerst das Routing-Add-on, damit das Yapaia-Hauptadd-on es bei
> seinem Start automatisch finden kann.

1. Im Add-on-Store **Yapaia Routing (GraphHopper)** anklicken
2. **Installieren** — der erste Build dauert 5–10 Minuten (Java + GraphHopper)
3. Im Tab **Konfiguration** anpassen:

   ```yaml
   region: germany
   pbf_url: https://download.geofabrik.de/europe/germany-latest.osm.pbf
   java_heap_gb: 4
   reimport_on_startup: false
   ```

   **Für DACH** (Deutschland + Österreich + Schweiz):
   ```yaml
   region: dach
   pbf_url: https://download.geofabrik.de/europe/dach-latest.osm.pbf
   java_heap_gb: 6
   ```

   > Geofabrik bietet ein direktes DACH-Bundle nicht überall an. Alternative:
   > drei einzelne Add-ons (geht nicht) ODER ein eigener pre-merged
   > `dach-latest.osm.pbf` (siehe `data/merge-dach.sh` im Repo) — auf
   > GitHub-Releases ablegen und URL hier eintragen.

4. **Speichern** → **Starten**
5. Tab **Log** öffnen und warten:
   - "Downloading OSM extract..." → 5–15 Min je nach Internet
   - "Started server: 0.0.0.0:8989" → fertig

> Der initiale OSM-Import läuft danach für ca. 20–40 Minuten. Während
> dieser Zeit antwortet GraphHopper noch nicht auf Routing-Anfragen.
> Im Log erscheinen Zeilen wie `flow encoder ... done`. **Add-on nicht
> neustarten** während des Imports.

---

## 5. Add-on 1: `Yapaia Go` installieren

1. Im Add-on-Store **Yapaia Go** anklicken
2. **Installieren** — Build dauert 3–5 Minuten (Frontend-Build inklusive)
3. Im Tab **Konfiguration** zumindest folgende Werte setzen:

   ```yaml
   secret_key: ""                # leer = wird automatisch generiert
   admin_emails: "deine@email.de"
   graphhopper_url: ""           # leer = Auto-Discovery vom Routing-Add-on
   log_level: info
   ```

   **Falls externer GraphHopper:**
   ```yaml
   graphhopper_url: "https://yapaia.cloud"      # oder eigene URL
   ```

   **Optional — Google OAuth:**
   ```yaml
   google_client_id: "xxxxx.apps.googleusercontent.com"
   google_client_secret: "GOCSPX-xxxxx"
   ```

4. **Speichern** → **Starten**
5. Tab **Log** prüfen: `Started server process` + `Application startup complete`

---

## 6. Ingress-UI öffnen

In der HA-Seitenleiste erscheint jetzt ein neuer Eintrag **Yapaia Navi**
(zwischen den anderen Add-on-Einträgen). Anklicken → Yapaia öffnet sich
eingebettet in der HA-Oberfläche.

**Erstanmeldung:**

1. Yapaia-Login → **Registrieren**
2. E-Mail + Passwort + Anzeigename
3. Der erste registrierte User wird automatisch Admin (und die in
   `admin_emails` aufgeführten E-Mails ebenso).

**Erste Route testen:**

1. In der Suchleiste: "Berlin" als Start, "München" als Ziel
2. **Route** → es sollte eine Polyline auf der Karte erscheinen, sobald das
   Routing-Add-on fertig importiert hat

---

## 7. Optional: Mosquitto-Anbindung

Falls das offizielle **Mosquitto broker**-Add-on schon läuft, erkennt
Yapaia es **automatisch** beim Start (Supervisor-Service-Discovery via
`mqtt:want` in der `config.yaml`). Im Log erscheint:

```
INFO MQTT service detected: <host>:1883
```

Keine weitere Konfiguration nötig. Yapaia-Navigation-Daten werden dann unter
`navi/<user_id>/...`-Topics im Broker veröffentlicht und sind via
MQTT-Auto-Discovery in HA als Sensoren verfügbar (siehe
`addons/home_assistant`-Plugin in Yapaia).

---

## 8. Optional: USB-GPS

1. USB-GPS-Empfänger einstecken
2. HA → **Einstellungen** → **Hardware** → Liste der USB-Geräte prüfen
   (z. B. `/dev/ttyUSB0`)
3. Yapaia-Add-on → **Konfiguration**:
   ```yaml
   gps_serial_port: "/dev/ttyUSB0"
   gps_serial_baud: 9600
   ```
4. **Speichern** → Add-on **neustarten**
5. In Yapaia → **Einstellungen** → **GPS-Quelle** → "Server-USB" auswählen

---

## 9. Alternative: Lokales Klonen statt Repository-URL

Falls das Hinzufügen der Repository-URL im Add-on-Store aus irgendeinem
Grund nicht funktioniert, kann das Repo auch lokal geklont und als
"Lokale Add-ons" geladen werden:

1. SSH-Add-on installieren (oder das offizielle "Advanced SSH & Web Terminal")
2. Anmelden, dann:
   ```bash
   cd /addons
   git clone https://github.com/Apfelsafft/yapaia-hassio yapaia-src
   ln -s yapaia-src/yapaia          ./yapaia
   ln -s yapaia-src/yapaia-routing  ./yapaia_routing
   ```
3. **Einstellungen** → **Add-ons** → **Add-on-Store** → **⋮** → **Add-ons neu prüfen**
4. Beide Yapaia-Add-ons erscheinen jetzt unter "Lokale Add-ons"

---

## 10. Backup & Restore

- **Yapaia Go** (`backup: hot`): wird bei jedem HA-Backup live mitgesichert,
  ohne dass das Add-on gestoppt werden muss. Die SQLite-Datenbank
  (`/data/yapaia.db`) und der `secret_key` sind enthalten.
- **Yapaia Routing** (`backup: cold`): wird vor dem Backup gestoppt; der
  Graph-Cache und die OSM-PBF-Datei sind **vom Backup ausgeschlossen** (zu
  groß). Nach einem Restore muss der OSM-Import einmal neu laufen
  (`reimport_on_startup: true` setzen, starten, danach wieder auf `false`).

---

## 11. Troubleshooting

| Symptom | Ursache | Fix |
|---------|---------|-----|
| Add-ons erscheinen nicht im Store nach Hinzufügen des Repos | Supervisor-Cache veraltet oder Repo-URL falsch | Repository-URL prüfen; alternativ lokales Klonen aus Abschnitt 9 verwenden |
| "Routing-Service Timeout" im UI | Routing-Add-on ist noch nicht fertig mit Import / `graphhopper_url` falsch | Log des Routing-Add-ons prüfen; URL in `yapaia`-Optionen kontrollieren |
| Karten lädt nicht / 404 auf `/assets/...` | Frontend wurde ohne `YAPAIA_HA_INGRESS=1` gebaut | Add-on neu installieren (Image neu bauen) |
| "Mit Google anmelden" funktioniert nicht | Google OAuth Redirect-URI passt nicht | In der Google Cloud Console muss `<HA-URL>/api/hassio_ingress/<token>/api/auth/google/callback` als gültiger Redirect eingetragen werden. Token wechselt nicht — einmal kopieren genügt. |
| WebSocket schlägt fehl (`/ws/navigation`) | Ingress-Patch in `index.html` wurde nicht geladen | Browser-Cache leeren; falls weiterhin: in DevTools die Network-Tab prüfen — der WS sollte unter `wss://<ha>/api/hassio_ingress/<token>/ws/navigation` aufgebaut werden |
| GraphHopper crasht mit OutOfMemoryError | `java_heap_gb` zu klein | Auf 6 oder 8 erhöhen, Add-on neustarten |
| OSM-Download bricht ab | Geofabrik-Server temporär offline | Im Routing-Log prüfen, manuell via SSH die `.pbf` nach `/data/<region>-latest.osm.pbf` legen, Add-on starten |

---

## 12. Updates

Bei Push auf `main` baut die GitHub-Action neue Images und veröffentlicht
sie unter `ghcr.io/apfelsafft/yapaia-hassio/{arch}-{addon}`. Supervisor
zeigt das Update im Add-on-Store an. Update-Reihenfolge: **erst `yapaia`,
dann `yapaia-routing`** (das Kern-Add-on toleriert kurzzeitig fehlendes
Routing besser als umgekehrt).

---

## 13. Deinstallation

1. Beide Add-ons stoppen
2. **Deinstallieren** im jeweiligen Add-on-Tab
3. Falls auch alle Daten weg sollen:
   - Yapaia-DB liegt in `/data/yapaia.db` (im Add-on-Container) — wird
     automatisch mit gelöscht
   - GraphHopper-OSM-Daten unter `/data/*.osm.pbf` und `/data/graph-cache/`
     ebenso

---

## Zusammenfassung der Endpunkte (für Power-User)

```
HA-Sidebar → /api/hassio_ingress/<token>/        → nginx (yapaia, :8080)
                                                     ├── /api/* → uvicorn (:8000)
                                                     ├── /ws/*  → uvicorn (:8000)
                                                     └── /*     → /opt/yapaia/frontend-dist

yapaia (intern)  → http://a0d7b954-yapaia-routing:8989  → GraphHopper API

extern (optional, nur falls Port-Mapping aktiv):
   http://homeassistant.local:8989 → GraphHopper direkt
```
