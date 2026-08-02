# Yapaia Routing (GraphHopper)

Routing-Engine für das `Yapaia Go`-Add-on. Stellt die GraphHopper-API auf
Port 8989 bereit (intern für andere Add-ons; im LAN nur freigeben, wenn
ausdrücklich gewünscht).

## Hardware-Anforderungen

- **CPU:** x86_64 oder aarch64 (RPi 5 grenzwertig)
- **RAM:** ≥6 GB für Deutschland-Datensatz, ≥10 GB für DACH, ≥16 GB für Europa
- **Disk:** ≥20 GB freier Platz für OSM-PBF (~5 GB) + Graph-Cache (~10 GB)
- **Erstinitialisierung:** der OSM-Import dauert auf NUC-Klasse-Hardware
  ca. 20–40 Minuten. Add-on **nicht** während dieser Zeit neustarten.

## Konfiguration

| Option | Default | Bedeutung |
|--------|---------|-----------|
| `region` | `germany` | Welcher Datensatz geladen wird (`germany`/`dach`/`europe`/`custom`) |
| `pbf_url` | Geofabrik Germany | Download-URL des OSM-PBF |
| `java_heap_gb` | `4` | JVM-Heap in GB. **Mindestens 4 GB für Deutschland**, 6 GB empfohlen. |
| `reimport_on_startup` | `false` | Auf `true` setzen + Add-on neustarten erzwingt einen vollständigen Re-Import (z.B. nach OSM-Update). Danach wieder auf `false` setzen. |

## Erste Inbetriebnahme

1. Add-on installieren.
2. In den Optionen `region`, `pbf_url` und `java_heap_gb` an die eigene
   Hardware anpassen.
3. **Starten** — der erste Start lädt ~5 GB OSM-Daten und importiert das
   Routing-Netz. Die Log-Anzeige zeigt den Fortschritt.
4. Wenn im Log `Started server on 0.0.0.0:8989` erscheint, ist der Service
   bereit.
5. Im Yapaia-Add-on die Option `graphhopper_url` leer lassen (Auto-Discovery)
   oder explizit setzen auf
   `http://a0d7b954-yapaia-routing:8989` (HA Supervisor DNS).

## OSM-Daten aktualisieren

1. Add-on stoppen
2. Im SSH-Add-on:
   ```bash
   rm /data/<region>-latest.osm.pbf
   ```
3. In den Optionen `reimport_on_startup` auf `true` setzen
4. Add-on starten — der OSM-Datensatz wird neu geladen und der Graph neu importiert
5. Nach Abschluss `reimport_on_startup` wieder auf `false` setzen

## Backup-Verhalten

`backup: cold` — vor jedem Snapshot wird das Add-on gestoppt. Sinnvoll, weil
das Graph-Cache sonst inkonsistent gesichert würde. Das Graph-Cache und das
OSM-PBF sind via `backup_exclude` **vom Backup ausgeschlossen** (zu groß).
Backups sichern damit nur die Add-on-Konfiguration; nach Restore muss der
Re-Import einmal laufen.

## Support

GitHub Issues: <https://github.com/Apfelsafft/yapaia-hassio/issues>
