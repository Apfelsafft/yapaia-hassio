# Yapaia Go

Browserbasiertes Turn-by-Turn-Navi, vollständig lokal, eingebettet in die
Home-Assistant-Sidebar via Ingress.

## Voraussetzungen

- Home Assistant OS / Supervised
- Bei Bedarf: das **Yapaia Routing**-Add-on installieren ODER eine externe
  GraphHopper-URL angeben (siehe Option `graphhopper_url`)
- Optional: das offizielle **Mosquitto broker**-Add-on, falls MQTT-Features
  (HA-Auto-Discovery, MQTT-Kommandos) genutzt werden sollen

## Konfiguration

| Option | Pflicht | Bedeutung |
|--------|---------|-----------|
| `secret_key` | nein | JWT-Signaturschlüssel. Leer = wird einmalig generiert und unter `/data/secret_key` persistiert. |
| `admin_emails` | nein | Komma-getrennte Liste — diese E-Mail-Adressen werden beim Backend-Start auf Admin-Status promoviert. |
| `graphhopper_url` | nein | URL zur GraphHopper-Routing-API. Leer = Auto-Discovery des `yapaia-routing`-Add-ons. |
| `photon_url` | nein | URL zu einer Photon-Geocoding-Instanz. Leer = Nominatim-Fallback (extern). |
| `google_client_id` | nein | Google-OAuth-Client-ID (für "Mit Google anmelden"). |
| `google_client_secret` | nein | Google-OAuth-Client-Secret. |
| `gps_serial_port` | nein | z.B. `/dev/ttyUSB0` für USB-GPS-Empfänger. |
| `gps_serial_baud` | nein | Baudrate des seriellen GPS, Default 9600. |
| `log_level` | nein | `debug` / `info` / `warning` / `error` |

## Erste Schritte

1. Add-on installieren und **Starten**.
2. **In Sidebar öffnen** anklicken (Yapaia erscheint als eigener Tab).
3. Im Yapaia-Login: **Registrieren** — der erste User wird automatisch Admin.
4. Falls vorhanden: das `Yapaia Routing`-Add-on installieren und starten, dann
   im Yapaia-UI eine Route berechnen lassen.

## Datenpersistenz

Alles unter `/data` ist persistent und wird in HA-Backups eingeschlossen
(Mode: hot). Insbesondere:

- `/data/yapaia.db` — SQLite-Datenbank (User, Fahrzeuge, Favoriten, Add-on-State)
- `/data/secret_key` — JWT-Signaturschlüssel

## Bekannte Einschränkungen

- Der bundled Marketplace (für Premium-Add-ons) ist im Add-on-Kontext
  deaktiviert. Premium-Add-ons können installiert werden, wenn eine externe
  Marketplace-URL über die Add-on-Optionen ergänzt wird (geplant für Folgereleases).
- Mehrere Yapaia-Instanzen auf einem HA-Host werden nicht unterstützt (würden
  sich um Port-/Ingress-Slot streiten).

## Support

GitHub Issues: <https://github.com/Apfelsafft/yapaia-hassio/issues>
