import { defineStore } from "pinia";
import { ref } from "vue";
import { useUserStore } from "./user";

export interface Preferences {
  default_profile?: "car" | "motorhome" | "bike" | "foot" | "motorcycle";
  gps_source?: "browser" | "server" | "url" | "simulate";
  map_pitch?: 0 | 60;
  map_bearing_mode?: "north" | "heading";
  tts_enabled?: boolean;
  default_vehicle_id?: string;
  alt_backend_url?: string;
  routing_mode?: "fastest" | "shortest" | "curvy" | "very_curvy";
  // Tankstellen
  stations_enabled?: boolean;
  stations_radius?: number;   // km, default 5
  stations_fuel?: string;     // e5 | e10 | diesel — override, falls kein Fahrzeug aktiv
  // Kartenstile (mapstyle add-on)
  map_style_light?: string;
  map_style_dark?: string;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const _LS_ALT_KEY = "navi_alt_backend";

export const usePreferencesStore = defineStore("preferences", () => {
  const userStore = useUserStore();
  const data = ref<Preferences>({});
  const loaded = ref(false);

  // Debounce writes so rapid UI changes don't hammer the backend.
  let saveTimer: ReturnType<typeof setTimeout> | null = null;
  let pending: Preferences = {};

  function _syncAltBackendToStorage(prefs: Preferences) {
    const url = prefs.alt_backend_url ?? "";
    if (url) localStorage.setItem(_LS_ALT_KEY, url);
    else localStorage.removeItem(_LS_ALT_KEY);
  }

  async function load() {
    if (!userStore.isLoggedIn) {
      data.value = {};
      loaded.value = false;
      return;
    }
    try {
      const resp = await fetch(`${_BACKEND}/api/preferences/`, { headers: userStore.authHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data.value = await resp.json();
      _syncAltBackendToStorage(data.value);
      loaded.value = true;
    } catch {
      // Silently degrade — preferences are non-critical, defaults apply.
      loaded.value = true;
    }
  }

  function reset() {
    data.value = {};
    loaded.value = false;
  }

  async function flushSave() {
    if (Object.keys(pending).length === 0) return;
    const body = pending;
    pending = {};
    try {
      const resp = await fetch(`${_BACKEND}/api/preferences/`, {
        method: "PUT",
        headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (resp.ok) {
        data.value = await resp.json();
        _syncAltBackendToStorage(data.value);
      }
    } catch {
      // Ignore; local state remains, retried next time.
    }
  }

  function set<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    if (data.value[key] === value) return;
    data.value = { ...data.value, [key]: value };
    pending = { ...pending, [key]: value };
    // alt_backend_url sofort in localStorage schreiben (für Offline-Zugriff)
    if (key === "alt_backend_url") _syncAltBackendToStorage(data.value);
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSave, 500);
  }

  return { data, loaded, load, reset, set };
});
