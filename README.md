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

## Älterer Single-Add-on-Versuch

Unter [`legacy/`](legacy/) liegt der erste, inzwischen abgelöste
Single-Add-on-Ansatz (ein Add-on statt zwei, ohne SQLite-/Ingress-Anpassungen).
Er wird nicht mehr aktiv gepflegt und dient nur als Referenz.
