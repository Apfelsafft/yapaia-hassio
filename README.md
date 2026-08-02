# Yapaia Go — Home Assistant Add-ons

Dieses Repository enthält **zwei** Home-Assistant-Supervisor-Add-ons, die
Yapaia Go als installierbare Komponenten im HA-Add-on-Store bereitstellen:

| Add-on | Slug | Zweck | Hardware-Bedarf |
|--------|------|-------|------------------|
| **Yapaia Go** | `yapaia` | UI + Backend + SQLite, eingebettet in HA-Sidebar via Ingress | gering (≈300 MB RAM, 200 MB Disk) |
| **Yapaia Routing** | `yapaia_routing` | GraphHopper-Routing-Engine (optional) | hoch (≈6 GB RAM, ≥20 GB Disk für DACH) |

Anwender, die nur die UI/Backend brauchen und ein bestehendes
GraphHopper auf einem VPS/Mini-PC nutzen, installieren nur das Kern-Add-on
und tragen die externe Routing-URL in den Add-on-Optionen ein. Wer Yapaia
komplett lokal auf der HA-Box betreiben will, installiert beide.

Der eigentliche Anwendungscode (Backend, Frontend, Addons) stammt aus dem
Hauptrepo [`Apfelsafft/Navi`](https://github.com/Apfelsafft/Navi) und ist
hier je Add-on vendored (`yapaia/backend`, `yapaia/frontend`,
`yapaia/addons`, `yapaia-routing/graphhopper`), damit jedes Add-on einen
in sich geschlossenen Docker-Build-Kontext hat — genau das Layout, das der
HA-Supervisor für Multi-Add-on-Repositories erwartet.

---

## Repository in Home Assistant hinzufügen

1. Home Assistant öffnen → **Einstellungen → Add-ons → Add-on-Store**
2. Rechts oben das **⋮**-Menü → **Repositories**
3. URL eintragen:
   ```
   https://github.com/Apfelsafft/yapaia-hassio
   ```
4. **Hinzufügen** klicken
5. Nach kurzer Wartezeit erscheinen die zwei Yapaia-Add-ons im Store

---

## Lokales Testen (vor Veröffentlichung)

Auf einem HA-OS-System mit SSH-Add-on:

```bash
cd /addons

git clone https://github.com/Apfelsafft/yapaia-hassio yapaia-src
ln -s yapaia-src/yapaia          ./yapaia
ln -s yapaia-src/yapaia-routing  ./yapaia_routing

# Im HA-UI: Einstellungen → Add-ons → Add-on-Store → ⋮ → "Lokale Add-ons neu laden"
```

Beide Add-ons erscheinen jetzt unter "Lokale Add-ons" und können installiert
werden.

---

## Installation und Konfiguration

Siehe die einzelnen `DOCS.md`-Dateien in den Add-on-Unterordnern:

- [yapaia/DOCS.md](yapaia/DOCS.md)
- [yapaia-routing/DOCS.md](yapaia-routing/DOCS.md)

Eine ausführliche End-to-End-Installationsanleitung mit Beispielwerten,
Reihenfolge der Installation und Troubleshooting findet sich in
[docs/HOME_ASSISTANT_ADDON_INSTALL.md](docs/HOME_ASSISTANT_ADDON_INSTALL.md).

Eine Recherche-/Konzept-Doku zum Hintergrund ("Yapaia als HA-Add-on") liegt
in [docs/HOME_ASSISTANT_ADDON.md](docs/HOME_ASSISTANT_ADDON.md).

---

## Standalone-Betrieb ohne Home Assistant (z. B. auf einem VPS)

Die Container basieren auf HA-Base-Images (`bashio`), lassen sich aber auch
ohne Supervisor per Docker Compose betreiben — `bashio::config` liest dazu
lokal aus `/data/options.json`, die man selbst anlegt.

```bash
git clone https://github.com/apfelsafft/yapaia-hassio.git
cd yapaia-hassio

mkdir -p data/yapaia data/routing
cp yapaia/options.json.example data/yapaia/options.json
cp yapaia-routing/options.json.example data/routing/options.json
# Werte in beiden Dateien nach Bedarf anpassen (z. B. admin_emails, region)

docker compose -f docker-compose.standalone.yml up -d --build
```

Yapaia Go ist danach unter `http://<VPS-IP>:8080` erreichbar, die
GraphHopper-API unter Port 8989. Der erste Start des Routing-Containers lädt
die OSM-Daten herunter und importiert den Graph (bei `region: germany`
ca. 20–40 Minuten) — Fortschritt mit `docker compose -f
docker-compose.standalone.yml logs -f yapaia-routing` verfolgen.

**Einschränkungen gegenüber dem echten Add-on:** Die MQTT-Auto-Discovery über
`bashio::services mqtt` und Ingress funktionieren nur unter dem HA
Supervisor. Für MQTT im Standalone-Betrieb müssen `MQTT_HOST` /
`MQTT_PORT` / `MQTT_USERNAME` / `MQTT_PASSWORD` manuell als
`environment:`-Variablen im Compose-File ergänzt werden.

---

## Älterer Single-Add-on-Versuch

Unter [`legacy/`](legacy/) liegt der erste, inzwischen abgelöste
Single-Add-on-Ansatz (ein Add-on statt zwei, ohne SQLite-/Ingress-Anpassungen).
Er wird nicht mehr aktiv gepflegt und dient nur als Referenz.
