import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { SearchResult } from "./map";
import { useUserStore } from "./user";

export interface Favorite {
  id: string;
  kind: "home" | "work" | "custom";
  label: string;     // display name: "Zuhause" / "Arbeit" / user-given
  address: string;   // geocoded address (real location text)
  lat: number;
  lon: number;
  type: string;
  show_chip: boolean;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

export const useFavoritesStore = defineStore("favorites", () => {
  const userStore = useUserStore();
  const items = ref<Favorite[]>([]);
  const loaded = ref(false);
  const error = ref<string | null>(null);

  const home = computed(() => items.value.find((f) => f.kind === "home") ?? null);
  const work = computed(() => items.value.find((f) => f.kind === "work") ?? null);
  const custom = computed(() => items.value.filter((f) => f.kind === "custom"));

  function toSearchResult(f: Favorite): SearchResult {
    // Prefer the real address as the label shown in the search input —
    // falls back to the display name for legacy entries without address.
    return { label: f.address || f.label, lat: f.lat, lon: f.lon, type: f.type };
  }

  async function load() {
    if (!userStore.isLoggedIn) {
      items.value = [];
      loaded.value = false;
      return;
    }
    try {
      const resp = await fetch(`${_BACKEND}/api/favorites/`, { headers: userStore.authHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      items.value = await resp.json();
      loaded.value = true;
      error.value = null;
    } catch (e) {
      error.value = (e as Error).message;
    }
  }

  function reset() {
    items.value = [];
    loaded.value = false;
  }

  async function setSpecial(kind: "home" | "work", r: SearchResult) {
    const displayName = kind === "home" ? "Zuhause" : "Arbeit";
    const body = {
      kind,
      label: displayName,
      address: r.label,
      lat: r.lat,
      lon: r.lon,
      type: r.type,
      show_chip: true,
    };
    const resp = await fetch(`${_BACKEND}/api/favorites/`, {
      method: "POST",
      headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const saved: Favorite = await resp.json();
    // Reactive replace/insert: splice triggers reactivity reliably on
    // proxied arrays where direct index assignment can be missed.
    const idx = items.value.findIndex((f) => f.kind === kind);
    if (idx >= 0) items.value.splice(idx, 1, saved);
    else items.value.unshift(saved);
  }

  async function add(label: string, r: SearchResult) {
    const body = {
      kind: "custom",
      label,
      address: r.label,
      lat: r.lat,
      lon: r.lon,
      type: r.type,
      show_chip: true,
    };
    const resp = await fetch(`${_BACKEND}/api/favorites/`, {
      method: "POST",
      headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const saved: Favorite = await resp.json();
    items.value.push(saved);
  }

  async function remove(id: string) {
    const resp = await fetch(`${_BACKEND}/api/favorites/${id}`, {
      method: "DELETE",
      headers: userStore.authHeaders(),
    });
    if (!resp.ok && resp.status !== 404) throw new Error(`HTTP ${resp.status}`);
    items.value = items.value.filter((f) => f.id !== id);
  }

  async function toggleChip(id: string) {
    const fav = items.value.find((f) => f.id === id);
    if (!fav) return;
    const newVal = !fav.show_chip;
    const resp = await fetch(`${_BACKEND}/api/favorites/${id}`, {
      method: "PATCH",
      headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ show_chip: newVal }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const saved: Favorite = await resp.json();
    const idx = items.value.findIndex((f) => f.id === id);
    if (idx >= 0) items.value.splice(idx, 1, saved);
  }

  function isFavorite(r: SearchResult | null): boolean {
    if (!r) return false;
    return items.value.some(
      (f) => Math.abs(f.lat - r.lat) < 0.0001 && Math.abs(f.lon - r.lon) < 0.0001
    );
  }

  return { items, home, work, custom, loaded, error, toSearchResult, setSpecial, add, remove, toggleChip, isFavorite, load, reset };
});
