import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useUserStore } from "./user";
import { usePreferencesStore } from "./preferences";
import { useVehiclesStore } from "./vehicles";
import { useAddonsStore } from "./addons";

export interface Station {
  id: string;
  name: string;
  brand: string;
  street: string;
  place: string;
  lat: number;
  lng: number;
  dist?: number;
  e5: number | false | null;
  e10: number | false | null;
  diesel: number | false | null;
  price?: number | false | null;
  isOpen: boolean;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

export const useStationsStore = defineStore("stations", () => {
  const userStore = useUserStore();
  const prefStore = usePreferencesStore();
  const vehiclesStore = useVehiclesStore();
  const addonsStore = useAddonsStore();

  const stations = ref<Station[]>([]);
  const loading = ref(false);
  const visible = ref(false);
  const error = ref<string | null>(null);

  // Is the tankerkoenig addon installed and has an API key configured?
  const addonInstalled = computed(() => addonsStore.isInstalled("tankerkoenig"));
  const apiEnabled = computed(() => {
    if (!addonInstalled.value) return false;
    const s = addonsStore.getAddonSettings("tankerkoenig");
    return Boolean(s.api_key);
  });

  // Active fuel: vehicle profile → addon setting → "e5"
  const activeFuel = computed((): string => {
    const vid = prefStore.data.default_vehicle_id;
    if (vid) {
      const v = vehiclesStore.items.find((x) => x.id === vid);
      if (v?.fuel_type && v.fuel_type !== "electric" && v.fuel_type !== "lpg") {
        return v.fuel_type;
      }
    }
    const addonSetting = addonsStore.getAddonSettings("tankerkoenig");
    return (addonSetting.fuel_type as string) ?? prefStore.data.stations_fuel ?? "e5";
  });

  const fuelLabel = computed(() => {
    const map: Record<string, string> = { e5: "Super E5", e10: "Super E10", diesel: "Diesel" };
    return map[activeFuel.value] ?? activeFuel.value.toUpperCase();
  });

  const cheapest = computed((): Station | null => {
    const open = stations.value.filter((s) => s.isOpen);
    if (!open.length) return null;
    return open.reduce((best, s) => {
      const bprice = _price(best, activeFuel.value);
      const sprice = _price(s, activeFuel.value);
      return sprice > 0 && sprice < bprice ? s : best;
    });
  });

  function _price(s: Station, fuel: string): number {
    const raw = fuel === "e5" ? s.e5 : fuel === "e10" ? s.e10 : s.diesel;
    return typeof raw === "number" && raw > 0 ? raw : 999;
  }

  function _addonRadius(): number {
    const s = addonsStore.getAddonSettings("tankerkoenig");
    return Number(s.radius ?? prefStore.data.stations_radius ?? 5);
  }

  async function fetchNearby(lat: number, lon: number) {
    if (!userStore.isLoggedIn || !addonInstalled.value) return;
    const radius = _addonRadius();
    loading.value = true;
    error.value = null;
    try {
      const resp = await fetch(
        `${_BACKEND}/api/addons/tankerkoenig/nearby?lat=${lat}&lon=${lon}&radius=${radius}&fuel=${activeFuel.value}`,
        { headers: userStore.authHeaders() }
      );
      if (resp.status === 503) {
        error.value = "Tankerkönig API-Key nicht konfiguriert";
        return;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      stations.value = data.stations ?? [];
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Fehler beim Laden der Tankstellen";
    } finally {
      loading.value = false;
    }
  }

  async function fetchAlongRoute(coordinates: number[][]) {
    if (!userStore.isLoggedIn || !addonInstalled.value) return;
    const radius = _addonRadius();
    loading.value = true;
    error.value = null;
    try {
      const resp = await fetch(`${_BACKEND}/api/addons/tankerkoenig/route`, {
        method: "POST",
        headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          coordinates,
          radius,
          fuel: activeFuel.value,
          corridor: 2.0,
        }),
      });
      if (resp.status === 503) {
        error.value = "Tankerkönig API-Key nicht konfiguriert";
        return;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      stations.value = data.stations ?? [];
    } catch (e) {
      error.value = e instanceof Error ? e.message : "Fehler beim Laden der Tankstellen";
    } finally {
      loading.value = false;
    }
  }

  function setVisible(v: boolean) {
    visible.value = v;
    prefStore.set("stations_enabled", v);
  }

  function toggle() {
    setVisible(!visible.value);
  }

  function clear() {
    stations.value = [];
    error.value = null;
  }

  return {
    stations,
    loading,
    visible,
    apiEnabled,
    addonInstalled,
    error,
    activeFuel,
    fuelLabel,
    cheapest,
    fetchNearby,
    fetchAlongRoute,
    setVisible,
    toggle,
    clear,
  };
});
