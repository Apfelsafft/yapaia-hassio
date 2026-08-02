import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useUserStore } from "./user";

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

export interface SettingsField {
  key: string;
  type: "text" | "password" | "number" | "boolean" | "select" | "range";
  label: string;
  required?: boolean;
  default?: unknown;
  placeholder?: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
}

export interface AddonManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  icon: string;
  author: string;
  category: string;
  capabilities: string[];
  settings_schema: SettingsField[];
  license_status?: string;
  code_missing?: boolean;
}

export interface MarketplaceEntry {
  id: string;
  name: string;
  version: string;
  description: string;
  icon: string;
  author: string;
  category: string;
  price?: number;       // 0 = free, >0 = paid
  requires_license?: boolean;
}

export const useAddonsStore = defineStore("addons", () => {
  const userStore = useUserStore();

  const installed = ref<AddonManifest[]>([]);
  const catalog = ref<MarketplaceEntry[]>([]);
  const settings = ref<Record<string, Record<string, unknown>>>({});
  const loadingInstall = ref<string | null>(null);
  const loadingUninstall = ref<string | null>(null);
  const catalogLoading = ref(false);

  const installedIds = computed(() => new Set(installed.value.map((a) => a.id)));

  function isInstalled(id: string): boolean {
    return installedIds.value.has(id);
  }

  async function fetchInstalled() {
    if (!userStore.isLoggedIn) return;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/installed`, {
        headers: userStore.authHeaders(),
      });
      if (resp.ok) installed.value = await resp.json();
    } catch { /* ignore */ }
  }

  async function fetchCatalog() {
    if (!userStore.isLoggedIn) return;
    catalogLoading.value = true;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/marketplace/catalog`, {
        headers: userStore.authHeaders(),
      });
      if (resp.ok) catalog.value = await resp.json();
    } catch { /* ignore */ } finally {
      catalogLoading.value = false;
    }
  }

  async function fetchSettings(addonId: string) {
    if (!userStore.isLoggedIn) return;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/${addonId}/settings`, {
        headers: userStore.authHeaders(),
      });
      if (resp.ok) settings.value[addonId] = await resp.json();
    } catch { /* ignore */ }
  }

  async function saveSettings(addonId: string, data: Record<string, unknown>) {
    if (!userStore.isLoggedIn) return false;
    const resp = await fetch(`${_BACKEND}/api/addons/${addonId}/settings`, {
      method: "PUT",
      headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (resp.ok) settings.value[addonId] = data;
    return resp.ok;
  }

  async function install(
    addonId: string,
    licenseKey?: string,
  ): Promise<{ ok: boolean; message: string }> {
    loadingInstall.value = addonId;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/marketplace/install/${addonId}`, {
        method: "POST",
        headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ license_key: licenseKey || null }),
      });
      const body = await resp.json();
      if (resp.ok) await fetchInstalled();
      return { ok: resp.ok, message: body.message ?? body.detail ?? "Fehler" };
    } catch (e) {
      return { ok: false, message: String(e) };
    } finally {
      loadingInstall.value = null;
    }
  }

  async function uninstall(addonId: string): Promise<{ ok: boolean; message: string }> {
    loadingUninstall.value = addonId;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/${addonId}`, {
        method: "DELETE",
        headers: userStore.authHeaders(),
      });
      const body = await resp.json();
      if (resp.ok) {
        installed.value = installed.value.filter((a) => a.id !== addonId);
        if (addonId === "track_recorder") stopTrackPolling();
      }
      return { ok: resp.ok, message: body.detail ?? (resp.ok ? "Deinstalliert" : "Fehler") };
    } catch (e) {
      return { ok: false, message: String(e) };
    } finally {
      loadingUninstall.value = null;
    }
  }

  function getAddonSettings(addonId: string): Record<string, unknown> {
    return settings.value[addonId] ?? {};
  }

  // ── Track Recorder active-recording status ──────────────────────────────
  const trackRecorderActive = ref(false);
  const trackRecorderStats = ref<{ distance_km: number; start_time: string } | null>(null);
  let _trackPollTimer: ReturnType<typeof setInterval> | null = null;

  async function pollTrackRecorderStatus() {
    if (!userStore.isLoggedIn || !isInstalled("track_recorder")) return;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/track_recorder/active`, {
        headers: userStore.authHeaders(),
      });
      if (resp.ok) {
        const data = await resp.json();
        trackRecorderActive.value = !!data.active;
        trackRecorderStats.value = data.active
          ? { distance_km: data.distance_km, start_time: data.start_time }
          : null;
      }
    } catch { /* ignore */ }
  }

  function startTrackPolling() {
    if (_trackPollTimer) return;
    pollTrackRecorderStatus();
    _trackPollTimer = setInterval(pollTrackRecorderStatus, 10_000);
  }

  function stopTrackPolling() {
    if (_trackPollTimer) { clearInterval(_trackPollTimer); _trackPollTimer = null; }
    trackRecorderActive.value = false;
    trackRecorderStats.value = null;
  }

  function reset() {
    installed.value = [];
    catalog.value = [];
    settings.value = {};
    stopTrackPolling();
  }

  return {
    installed,
    catalog,
    settings,
    installedIds,
    catalogLoading,
    loadingInstall,
    loadingUninstall,
    isInstalled,
    fetchInstalled,
    fetchCatalog,
    fetchSettings,
    saveSettings,
    install,
    uninstall,
    getAddonSettings,
    reset,
    trackRecorderActive,
    trackRecorderStats,
    startTrackPolling,
    stopTrackPolling,
  };
});
