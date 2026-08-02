/**
 * Gibt die Basis-URL für Routing- und Geocoding-Anfragen zurück.
 * Priorität: UserPreference.alt_backend_url → localStorage → Standard-Backend
 *
 * Das erlaubt z.B. einen lokalen Raspberry Pi oder Mini-PC als Routing-Server
 * zu verwenden, wenn das Gerät im gleichen Netz ist.
 */

import { usePreferencesStore } from "../stores/preferences";

const _DEFAULT = import.meta.env.VITE_BACKEND_URL || "";
const _LS_KEY = "navi_alt_backend";

function _altUrl(): string {
  try {
    const url = usePreferencesStore().data.alt_backend_url ?? "";
    if (url) return url.replace(/\/$/, "");
  } catch {
    // Pinia noch nicht initialisiert (z.B. beim ersten Load)
  }
  return (localStorage.getItem(_LS_KEY) ?? "").replace(/\/$/, "");
}

export function routingUrl(): string {
  return _altUrl() || _DEFAULT;
}

export function searchUrl(): string {
  return _altUrl() || _DEFAULT;
}
