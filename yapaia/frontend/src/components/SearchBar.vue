<script setup lang="ts">
import { ref, watch, computed, watchEffect, nextTick, onMounted } from "vue";
import { useMapStore, type SearchResult } from "../stores/map";
import { useFavoritesStore, type Favorite } from "../stores/favorites";
import { useUserStore } from "../stores/user";
import { useUiStore } from "../stores/ui";
import { usePreferencesStore } from "../stores/preferences";
import { useVehiclesStore } from "../stores/vehicles";
import { useAddonsStore } from "../stores/addons";
import * as routing from "../services/routing";
import { searchUrl } from "../services/serviceUrl";
import AiNavInput from "./AiNavInput.vue";

const prefStore = usePreferencesStore();
const vehiclesStore = useVehiclesStore();

const store = useMapStore();
const favStore = useFavoritesStore();
const userStore = useUserStore();
const uiStore = useUiStore();
const addonsStore = useAddonsStore();
const backendUrl = import.meta.env.VITE_BACKEND_URL || "";

const aiNavInstalled = computed(() => addonsStore.isInstalled("navi_ai"));
const showAiInput = ref(false);

const fromQuery  = ref("");
const toQuery    = ref("");
const fromResults = ref<SearchResult[]>([]);
const toResults   = ref<SearchResult[]>([]);
const showFrom   = ref(false);
const showTo     = ref(false);
const fromLocked = ref(false);
const toLocked   = ref(false);
const fromError  = ref("");
const toError    = ref("");
const fromLoading = ref(false);
const toLoading   = ref(false);

// Save-to-favorites state
const saveFavFor   = ref<"from" | "to" | "waypoint" | null>(null);
const saveFavWpIdx = ref<number | null>(null);
const saveFavLabel = ref("");
const saveFavMode  = ref<"home" | "work" | "custom" | null>(null);

let fromTimer: ReturnType<typeof setTimeout> | null = null;
let toTimer:   ReturnType<typeof setTimeout> | null = null;

// Flags: prevent the query watcher from resetting state after a programmatic selection
let fromProgrammatic = false;
let toProgrammatic   = false;

// AbortControllers: cancel in-flight searches when the user picks a result or
// types a new query — prevents stale results from re-opening the dropdown
// after selection (which previously caused "first click is ignored").
let fromAbort: AbortController | null = null;
let toAbort:   AbortController | null = null;

// ── Waypoints ──────────────────────────────────────────────────────────────
const wpQueries  = ref<string[]>([]);
const wpResults  = ref<SearchResult[][]>([]);
const wpShow     = ref<boolean[]>([]);
const wpLocked   = ref<boolean[]>([]);
const wpLoading  = ref<boolean[]>([]);
const wpErrors   = ref<string[]>([]);
const wpAborts: (AbortController | null)[] = [];
const wpTimers:  (ReturnType<typeof setTimeout> | null)[] = [];

// ── Drag-to-reorder state ─────────────────────────────────────────────────
const draggingIdx = ref<number | null>(null);
const dragOverIdx = ref<number | null>(null);

// ── Focused field tracking (for favorite chip → focused input) ────────────
const focusedField = ref<"from" | "to" | number | null>(null);
let _focusClearTimer: ReturnType<typeof setTimeout> | null = null;

function onFieldFocus(field: "from" | "to" | number) {
  if (_focusClearTimer) { clearTimeout(_focusClearTimer); _focusClearTimer = null; }
  focusedField.value = field;
}

function onFieldBlur() {
  // Delay so a chip click fires before we lose the focused field info
  _focusClearTimer = setTimeout(() => { focusedField.value = null; }, 300);
}

// ── Auto-set origin to current GPS on mount (incl. after nav ends) ────────
let _autoOriginDone = false;
watch(() => store.userPosition, (pos) => {
  if (_autoOriginDone || !pos || fromLocked.value) return;
  _autoOriginDone = true;
  selectFrom({ label: "Mein Standort", lat: pos[1], lon: pos[0], type: "gps" });
}, { immediate: true });

// Sync UI arrays with store.waypoints length
watchEffect(() => {
  const len = store.waypoints.length;
  while (wpQueries.value.length < len) {
    wpQueries.value.push("");
    wpResults.value.push([]);
    wpShow.value.push(false);
    wpLocked.value.push(false);
    wpLoading.value.push(false);
    wpErrors.value.push("");
    wpAborts.push(null);
    wpTimers.push(null);
  }
  if (wpQueries.value.length > len) {
    wpQueries.value  = wpQueries.value.slice(0, len);
    wpResults.value  = wpResults.value.slice(0, len);
    wpShow.value     = wpShow.value.slice(0, len);
    wpLocked.value   = wpLocked.value.slice(0, len);
    wpLoading.value  = wpLoading.value.slice(0, len);
    wpErrors.value   = wpErrors.value.slice(0, len);
    wpAborts.splice(len);
    wpTimers.splice(len);
  }
});

function addWaypointRow() {
  store.addWaypoint({ label: "", lat: 0, lon: 0, type: "" });
}

function removeWaypointRow(idx: number) {
  if (wpAborts[idx]) wpAborts[idx]!.abort();
  if (wpTimers[idx]) clearTimeout(wpTimers[idx]!);
  store.removeWaypoint(idx);
}

function searchWaypoint(idx: number, q: string) {
  wpLocked.value[idx] = false;
  wpErrors.value[idx] = "";
  store.setWaypoint(idx, { label: q, lat: 0, lon: 0, type: "" });
  if (wpTimers[idx]) clearTimeout(wpTimers[idx]!);
  if (wpAborts[idx]) wpAborts[idx]!.abort();
  if (q.trim().length < 2) { wpResults.value[idx] = []; wpShow.value[idx] = false; return; }
  wpTimers[idx] = setTimeout(async () => {
    wpAborts[idx] = new AbortController();
    const sig = wpAborts[idx]!.signal;
    wpLoading.value[idx] = true;
    try {
      const results = await fetchResults(q, sig);
      if (sig.aborted) return;
      wpResults.value[idx] = results;
      wpShow.value[idx] = results.length > 0;
      if (results.length === 0) wpErrors.value[idx] = "Keine Treffer.";
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      wpErrors.value[idx] = "Adresssuche nicht erreichbar.";
    } finally {
      if (!sig.aborted) wpLoading.value[idx] = false;
    }
  }, 200);
}

function onWaypointBlur(idx: number) {
  setTimeout(() => { wpShow.value[idx] = false; }, 150);
}

function onWaypointEnter(idx: number) {
  if (wpResults.value[idx]?.length) selectWaypoint(idx, wpResults.value[idx][0]);
}

function selectWaypoint(idx: number, r: SearchResult) {
  if (wpTimers[idx]) clearTimeout(wpTimers[idx]!);
  if (wpAborts[idx]) wpAborts[idx]!.abort();
  store.setWaypoint(idx, r);
  wpQueries.value[idx]  = r.label;
  wpLocked.value[idx]   = true;
  wpShow.value[idx]     = false;
  wpErrors.value[idx]   = "";
  wpLoading.value[idx]  = false;
}

function _moveArr<T>(arr: T[], from: number, to: number): T[] {
  const copy = [...arr];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
}

function reorderLocalState(from: number, to: number) {
  wpQueries.value = _moveArr(wpQueries.value, from, to);
  wpResults.value = _moveArr(wpResults.value, from, to);
  wpShow.value    = _moveArr(wpShow.value,    from, to);
  wpLocked.value  = _moveArr(wpLocked.value,  from, to);
  wpLoading.value = _moveArr(wpLoading.value, from, to);
  wpErrors.value  = _moveArr(wpErrors.value,  from, to);
  const ab = _moveArr([...wpAborts], from, to);
  wpAborts.splice(0, wpAborts.length, ...ab);
  const tm = _moveArr([...wpTimers], from, to);
  wpTimers.splice(0, wpTimers.length, ...tm);
}

function onGripDown(event: PointerEvent, idx: number) {
  event.preventDefault();
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  draggingIdx.value = idx;
  dragOverIdx.value = idx;
}

function onGripMove(event: PointerEvent, idx: number) {
  if (draggingIdx.value !== idx) return;
  const el = document.elementFromPoint(event.clientX, event.clientY);
  const row = el?.closest("[data-wp-idx]") as HTMLElement | null;
  if (row?.dataset.wpIdx !== undefined) {
    dragOverIdx.value = parseInt(row.dataset.wpIdx);
  }
}

function onGripUp(event: PointerEvent, idx: number) {
  if (draggingIdx.value !== idx) return;
  const from = draggingIdx.value;
  const to   = dragOverIdx.value ?? from;
  draggingIdx.value = null;
  dragOverIdx.value = null;
  if (from !== to) {
    reorderLocalState(from, to);
    store.reorderWaypoints(from, to);
  }
}

function onGripCancel() {
  draggingIdx.value = null;
  dragOverIdx.value = null;
}

async function fetchResults(q: string, signal: AbortSignal): Promise<SearchResult[]> {
  if (q.trim().length < 2) return [];
  const resp = await fetch(`${searchUrl()}/api/search?q=${encodeURIComponent(q)}&limit=6`, { signal });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const data = await resp.json();
  return data.results ?? [];
}

function typeIcon(type: string): string {
  if (!type) return "📍";
  if (["city", "town", "village", "hamlet"].includes(type)) return "🏙️";
  if (["motorway", "trunk", "primary", "secondary", "tertiary", "street", "residential"].includes(type)) return "🛣️";
  if (["railway", "station", "halt"].includes(type)) return "🚂";
  if (["aerodrome", "airport"].includes(type)) return "✈️";
  if (["hotel", "hostel"].includes(type)) return "🏨";
  if (["restaurant", "cafe", "fast_food"].includes(type)) return "🍽️";
  if (["fuel"].includes(type)) return "⛽";
  if (["hospital", "clinic"].includes(type)) return "🏥";
  if (["parking"].includes(type)) return "🅿️";
  return "📍";
}

// ── From ──────────────────────────────────────────────────────────────────
watch(fromQuery, (q) => {
  if (fromProgrammatic) { fromProgrammatic = false; return; }
  fromLocked.value = false;
  fromError.value = "";
  store.setOrigin(null);
  if (fromTimer) clearTimeout(fromTimer);
  if (fromAbort) fromAbort.abort();
  if (q.trim().length < 2) { fromResults.value = []; showFrom.value = false; return; }
  fromTimer = setTimeout(async () => {
    fromAbort = new AbortController();
    const sig = fromAbort.signal;
    fromLoading.value = true;
    try {
      const results = await fetchResults(q, sig);
      if (sig.aborted) return;
      fromResults.value = results;
      showFrom.value = results.length > 0;
      if (results.length === 0) fromError.value = "Keine Treffer.";
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      fromError.value = "Adresssuche nicht erreichbar.";
    } finally {
      if (!sig.aborted) fromLoading.value = false;
    }
  }, 200);
});

function selectFrom(r: SearchResult) {
  if (fromTimer) clearTimeout(fromTimer);
  if (fromAbort) fromAbort.abort();
  fromProgrammatic = true;
  store.setOrigin(r);
  fromQuery.value = r.label;
  fromLocked.value = true;
  fromError.value = "";
  fromLoading.value = false;
  showFrom.value = false;
  saveFavFor.value = null;
}

function onFromEnter() {
  if (fromResults.value.length > 0) selectFrom(fromResults.value[0]);
}

function onFromBlur() {
  setTimeout(() => { showFrom.value = false; }, 150);
}

// ── To ────────────────────────────────────────────────────────────────────
watch(toQuery, (q) => {
  if (toProgrammatic) { toProgrammatic = false; return; }
  toLocked.value = false;
  toError.value = "";
  store.setDestination(null);
  if (toTimer) clearTimeout(toTimer);
  if (toAbort) toAbort.abort();
  if (q.trim().length < 2) { toResults.value = []; showTo.value = false; return; }
  toTimer = setTimeout(async () => {
    toAbort = new AbortController();
    const sig = toAbort.signal;
    toLoading.value = true;
    try {
      const results = await fetchResults(q, sig);
      if (sig.aborted) return;
      toResults.value = results;
      showTo.value = results.length > 0;
      if (results.length === 0) toError.value = "Keine Treffer.";
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      toError.value = "Adresssuche nicht erreichbar.";
    } finally {
      if (!sig.aborted) toLoading.value = false;
    }
  }, 200);
});

function selectTo(r: SearchResult) {
  if (toTimer) clearTimeout(toTimer);
  if (toAbort) toAbort.abort();
  toProgrammatic = true;
  store.setDestination(r);
  toQuery.value = r.label;
  toLocked.value = true;
  toError.value = "";
  toLoading.value = false;
  showTo.value = false;
  saveFavFor.value = null;
}

function onToEnter() {
  if (toResults.value.length > 0) selectTo(toResults.value[0]);
}

function onToBlur() {
  setTimeout(() => { showTo.value = false; }, 150);
}

// ── Clear helpers ─────────────────────────────────────────────────────────
function clearFrom() {
  fromProgrammatic = true;
  fromQuery.value = "";
  fromLocked.value = false;
  fromError.value = "";
  fromResults.value = [];
  showFrom.value = false;
  store.setOrigin(null);
  saveFavFor.value = null;
}

function clearTo() {
  toProgrammatic = true;
  toQuery.value = "";
  toLocked.value = false;
  toError.value = "";
  toResults.value = [];
  showTo.value = false;
  store.setDestination(null);
  saveFavFor.value = null;
}

// ── Favorites ─────────────────────────────────────────────────────────────
function openSaveFav(target: "from" | "to" | "waypoint", wpIdx?: number) {
  saveFavFor.value = target;
  saveFavWpIdx.value = wpIdx ?? null;
  saveFavMode.value = null;
  const r = target === "to" ? store.destination
          : target === "from" ? store.origin
          : (wpIdx !== undefined ? store.waypoints[wpIdx] : null);
  saveFavLabel.value = r?.label ?? "";
}

function closeSaveFav() {
  saveFavFor.value = null;
  saveFavWpIdx.value = null;
  saveFavMode.value = null;
  saveFavLabel.value = "";
}

function commitSaveFav() {
  const r = saveFavFor.value === "to" ? store.destination
          : saveFavFor.value === "from" ? store.origin
          : (saveFavWpIdx.value !== null ? store.waypoints[saveFavWpIdx.value] : null);
  if (!r || !saveFavMode.value) return;
  if (saveFavMode.value === "home") {
    favStore.setSpecial("home", r);
  } else if (saveFavMode.value === "work") {
    favStore.setSpecial("work", r);
  } else {
    const label = saveFavLabel.value.trim() || r.label;
    favStore.add(label, r);
  }
  closeSaveFav();
}

function applyFavAsFrom(f: Favorite | null) {
  if (!f) return;
  selectFrom(favStore.toSearchResult(f));
}

function applyFav(f: Favorite | null) {
  if (!f) return;
  const r = favStore.toSearchResult(f);
  const target = focusedField.value;
  if (target === "from") selectFrom(r);
  else if (typeof target === "number") selectWaypoint(target, r);
  else selectTo(r);
}

// ── Collapsible ───────────────────────────────────────────────────────────
const collapsed = ref(false);

// ── Map long-press pick ────────────────────────────────────────────────────
watch(() => store.mapPickPending, async (pick) => {
  if (!pick) return;
  collapsed.value = false;
  if (pick.target === "origin") {
    selectFrom(pick.result);
  } else if (pick.target === "destination") {
    selectTo(pick.result);
  } else if (pick.target === "waypoint") {
    addWaypointRow();
    await nextTick();
    selectWaypoint(store.waypoints.length - 1, pick.result);
  }
  store.mapPickPending = null;
});

// ── Swap ──────────────────────────────────────────────────────────────────
function swapFromTo() {
  fromProgrammatic = true;
  toProgrammatic = true;
  [fromQuery.value, toQuery.value] = [toQuery.value, fromQuery.value];
  [fromLocked.value, toLocked.value] = [toLocked.value, fromLocked.value];
  [fromError.value, toError.value] = [toError.value, fromError.value];
  const tmpOrigin = store.origin;
  store.setOrigin(store.destination);
  store.setDestination(tmpOrigin);
  showFrom.value = false;
  showTo.value = false;
}

// ── Route ─────────────────────────────────────────────────────────────────
function vehicleIcon(type: string): string {
  if (type === "motorhome") return "🚐";
  if (type === "motorcycle") return "🏍️";
  if (type === "bike") return "🚲";
  return "🚗";
}

const profileOptions = computed(() => {
  const vehicleOpts = vehiclesStore.items.map(v => ({
    value: `v:${v.id}`,
    label: `${vehicleIcon(v.type)} ${v.name}`,
  }));
  const hasMotorhome   = vehiclesStore.items.some(v => v.type === "motorhome");
  const hasMotorcycle  = vehiclesStore.items.some(v => v.type === "motorcycle");
  const generic = [
    { value: "car",        label: "🚗 PKW" },
    ...(hasMotorcycle  ? [] : [{ value: "motorcycle", label: "🏍️ Motorrad" }]),
    ...(hasMotorhome   ? [] : [{ value: "motorhome",  label: "🚐 Wohnmobil" }]),
    { value: "bike",       label: "🚲 Fahrrad" },
    { value: "foot",       label: "🚶 Fuß" },
  ];
  return [...vehicleOpts, ...generic];
});

const profileSelection = computed({
  get: () => {
    const vid = prefStore.data.default_vehicle_id;
    if (vid && vehiclesStore.items.some(v => v.id === vid)) return `v:${vid}`;
    return prefStore.data.default_profile ?? "car";
  },
  set: (val: string) => {
    if (val.startsWith("v:")) {
      const id = val.slice(2);
      prefStore.set("default_vehicle_id", id);
      const v = vehiclesStore.items.find(x => x.id === id);
      if (v) prefStore.set("default_profile", v.type as "car" | "motorhome" | "bike" | "foot" | "motorcycle");
    } else {
      prefStore.set("default_vehicle_id", "");
      prefStore.set("default_profile", val as "car" | "motorhome" | "bike" | "foot" | "motorcycle");
    }
  },
});

const hasUnlockedWaypoints = computed(() =>
  store.waypoints.some((wp, i) => !wpLocked.value[i] || (wp.lat === 0 && wp.lon === 0))
);

const routingModes = [
  { value: "fastest",    icon: "🚀", label: "Schnellste" },
  { value: "shortest",   icon: "📏", label: "Kürzeste" },
  { value: "curvy",      icon: "🛣️",  label: "Kurvig" },
  { value: "very_curvy", icon: "🏔️", label: "Sehr kurvig" },
] as const;

async function calculateRoute() {
  if (!store.origin || !store.destination || hasUnlockedWaypoints.value) return;
  store.isLoading = true;
  store.error = null;
  store.clearRoute();
  try {
    await routing.calculateRoute();
  } catch (e) {
    store.error = e instanceof Error ? e.message : "Unbekannter Fehler";
  } finally {
    store.isLoading = false;
  }
}

function useMyLocation() {
  // If GPS is already tracked by any source, use it immediately
  if (store.userPosition) {
    const [lon, lat] = store.userPosition;
    selectFrom({ label: "Mein Standort", lat, lon, type: "gps" });
    return;
  }
  if (!("geolocation" in navigator)) {
    fromError.value = "Geolocation wird von diesem Browser nicht unterstützt.";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      selectFrom({
        label: "Mein Standort",
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        type: "gps",
      });
    },
    (err) => {
      if (err.code === 1) {
        fromError.value = "Standortzugriff verweigert. iPhone: Einstellungen → Datenschutz → Ortungsdienste → Browser → Beim Verwenden der App.";
      } else if (err.code === 2) {
        fromError.value = "Standort konnte nicht ermittelt werden – bitte GPS aktivieren.";
      } else {
        fromError.value = "GPS-Zeitüberschreitung – bitte erneut versuchen.";
      }
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
  );
}

// ── KI-Navigation ─────────────────────────────────────────────────────────
function handleAiApply(payload: {
  destination: SearchResult;
  waypoints: SearchResult[];
  profile: string;
  avoid: string[];
  routing_strategy: string;
  notes: string;
}) {
  showAiInput.value = false;
  collapsed.value = false;

  // Apply profile
  if (payload.profile) {
    prefStore.set("default_profile", payload.profile as "car" | "motorhome" | "bike" | "foot");
    prefStore.set("default_vehicle_id", "");
  }

  // Apply origin if user has GPS, otherwise leave empty
  if (store.userPosition) {
    const [lon, lat] = store.userPosition;
    selectFrom({ label: "Mein Standort", lat, lon, type: "gps" });
  }

  // Clear existing waypoints
  while (store.waypoints.length > 0) store.removeWaypoint(0);

  // Apply waypoints — addWaypointRow() adds a blank slot + store entry,
  // then we overwrite with the geocoded result via selectWaypoint()
  for (const wp of payload.waypoints) {
    addWaypointRow();
    const idx = store.waypoints.length - 1;
    if (idx >= 0) selectWaypoint(idx, wp);
  }

  // Apply destination
  selectTo(payload.destination);
}
</script>

<template>
  <div class="search-panel" :class="{ 'search-panel--collapsed': collapsed }">
    <!-- Header: always visible -->
    <div class="panel-header">
      <button class="panel-toggle" @click="collapsed = !collapsed" :title="collapsed ? 'Routenplaner öffnen' : 'Minimieren'">
        <svg v-if="collapsed" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <polyline points="18 15 12 9 6 15"/>
        </svg>
      </button>
      <span v-if="!collapsed" class="panel-label">Route planen</span>
      <button
        v-if="aiNavInstalled"
        class="ai-btn"
        :class="{ active: showAiInput }"
        @click="showAiInput = !showAiInput"
        title="KI-Navigation"
      >✨</button>
      <button class="settings-btn" @click="uiStore.settingsOpen = true" title="Einstellungen">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>

    <!-- Content: hidden when collapsed -->
    <div v-show="!collapsed" class="panel-content">

    <!-- KI-Navigation -->
    <AiNavInput
      v-if="showAiInput && aiNavInstalled"
      @apply="handleAiApply"
      @close="showAiInput = false"
    />

    <!-- Von -->
    <div class="input-row">
      <button class="icon-btn" title="Aktuellen Standort verwenden" @click="useMyLocation">📍</button>
      <div class="autocomplete">
        <div class="input-wrap" :class="{ locked: fromLocked, error: fromError && !showFrom }">
          <button
            class="star-btn"
            :class="{ saved: fromLocked && favStore.isFavorite(store.origin) }"
            :disabled="!fromLocked"
            @mousedown.prevent="openSaveFav('from')"
            title="Als Favorit speichern"
          >{{ fromLocked && favStore.isFavorite(store.origin) ? "★" : "☆" }}</button>
          <input
            v-model="fromQuery"
            placeholder="Von: Stadt, Adresse oder POI"
            @keydown.enter.prevent="onFromEnter"
            @focus="onFieldFocus('from'); showFrom = fromResults.length > 0"
            @blur="onFieldBlur(); onFromBlur()"
          />
          <span v-if="fromLoading" class="spinner">⟳</span>
          <button class="clear-btn" @mousedown.prevent="clearFrom" title="Eingabe löschen">✕</button>
        </div>
        <p v-if="fromError && !showFrom && !fromLoading" class="field-error">{{ fromError }}</p>
        <ul v-if="showFrom" class="dropdown">
          <li v-for="(r, i) in fromResults" :key="r.label + r.lat"
              :class="{ first: i === 0 }"
              @mousedown.prevent="selectFrom(r)">
            <span class="poi-icon">{{ typeIcon(r.type) }}</span>
            {{ r.label }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Swap Start ↔ Ziel + Zwischenziel hinzufügen -->
    <div class="swap-row">
      <button class="swap-btn" title="Start und Ziel tauschen" @click="swapFromTo">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="7 4 7 20 11 16"/>
          <polyline points="17 20 17 4 13 8"/>
        </svg>
      </button>
      <button
        v-if="store.origin && !store.isNavigating"
        class="add-via-btn"
        @click="addWaypointRow"
        title="Zwischenziel hinzufügen"
      >+ Zwischenziel</button>
    </div>

    <!-- Zwischenziele -->
    <template v-for="(wp, i) in store.waypoints" :key="'wp-' + i">
      <div
        class="input-row"
        :data-wp-idx="i"
        :class="{
          'wp-drag-source': draggingIdx === i,
          'wp-drag-over':   dragOverIdx === i && draggingIdx !== i,
        }"
      >
        <span
          class="icon-btn grip-handle"
          title="Zum Sortieren ziehen"
          @pointerdown="onGripDown($event, i)"
          @pointermove="onGripMove($event, i)"
          @pointerup="onGripUp($event, i)"
          @pointercancel="onGripCancel"
        >
          <svg width="14" height="12" viewBox="0 0 14 12" fill="currentColor" aria-hidden="true">
            <rect y="0"  width="14" height="2" rx="1"/>
            <rect y="5"  width="14" height="2" rx="1"/>
            <rect y="10" width="14" height="2" rx="1"/>
          </svg>
        </span>
        <div class="autocomplete">
          <div class="input-wrap" :class="{ locked: wpLocked[i], error: wpErrors[i] && !wpShow[i] }">
            <button
              class="star-btn"
              :class="{ saved: wpLocked[i] && favStore.isFavorite(store.waypoints[i]) }"
              :disabled="!wpLocked[i]"
              @mousedown.prevent="openSaveFav('waypoint', i)"
              title="Als Favorit speichern"
            >{{ wpLocked[i] && favStore.isFavorite(store.waypoints[i]) ? "★" : "☆" }}</button>
            <input
              v-model="wpQueries[i]"
              placeholder="Zwischenziel…"
              @input="searchWaypoint(i, wpQueries[i])"
              @keydown.enter.prevent="onWaypointEnter(i)"
              @focus="onFieldFocus(i); wpShow[i] = (wpResults[i]?.length ?? 0) > 0"
              @blur="onFieldBlur(); onWaypointBlur(i)"
            />
            <span v-if="wpLoading[i]" class="spinner">⟳</span>
            <button class="clear-btn" @mousedown.prevent="removeWaypointRow(i)" title="Zwischenziel entfernen">✕</button>
          </div>
          <p v-if="wpErrors[i] && !wpShow[i] && !wpLoading[i]" class="field-error">{{ wpErrors[i] }}</p>
          <ul v-if="wpShow[i]" class="dropdown">
            <li v-for="(r, j) in wpResults[i]" :key="r.label + r.lat"
                :class="{ first: j === 0 }"
                @mousedown.prevent="selectWaypoint(i, r)">
              <span class="poi-icon">{{ typeIcon(r.type) }}</span>
              {{ r.label }}
            </li>
          </ul>
        </div>
      </div>
    </template>

    <!-- Nach -->
    <div class="input-row">
      <span class="icon-btn">🏁</span>
      <div class="autocomplete">
        <div class="input-wrap" :class="{ locked: toLocked, error: toError && !showTo }">
          <button
            class="star-btn"
            :class="{ saved: toLocked && favStore.isFavorite(store.destination) }"
            :disabled="!toLocked"
            @mousedown.prevent="openSaveFav('to')"
            title="Als Favorit speichern"
          >{{ toLocked && favStore.isFavorite(store.destination) ? "★" : "☆" }}</button>
          <input
            v-model="toQuery"
            placeholder="Nach: Stadt, Adresse oder POI"
            @keydown.enter.prevent="onToEnter"
            @focus="onFieldFocus('to'); showTo = toResults.length > 0"
            @blur="onFieldBlur(); onToBlur()"
          />
          <span v-if="toLoading" class="spinner">⟳</span>
          <button class="clear-btn" @mousedown.prevent="clearTo" title="Eingabe löschen">✕</button>
        </div>
        <p v-if="toError && !showTo && !toLoading" class="field-error">{{ toError }}</p>
        <ul v-if="showTo" class="dropdown">
          <li v-for="(r, i) in toResults" :key="r.label + r.lat"
              :class="{ first: i === 0 }"
              @mousedown.prevent="selectTo(r)">
            <span class="poi-icon">{{ typeIcon(r.type) }}</span>
            {{ r.label }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Schnellzugriff Favoriten -->
    <div v-if="favStore.home?.show_chip || favStore.work?.show_chip || favStore.custom.some(f => f.show_chip)" class="fav-row">
      <div v-if="favStore.home?.show_chip" class="fav-chip-group">
        <button class="fav-chip-start" @click="applyFavAsFrom(favStore.home)" :title="`Als Start: ${favStore.home.address || favStore.home.label}`">↑</button>
        <button class="fav-chip-end" @click="applyFav(favStore.home)" :title="`In fokussiertes Feld einfügen: ${favStore.home.address || favStore.home.label}`">
          🏠 <span>Zuhause</span>
        </button>
      </div>
      <div v-if="favStore.work?.show_chip" class="fav-chip-group">
        <button class="fav-chip-start" @click="applyFavAsFrom(favStore.work)" :title="`Als Start: ${favStore.work.address || favStore.work.label}`">↑</button>
        <button class="fav-chip-end" @click="applyFav(favStore.work)" :title="`In fokussiertes Feld einfügen: ${favStore.work.address || favStore.work.label}`">
          💼 <span>Arbeit</span>
        </button>
      </div>
      <div v-for="f in favStore.custom.filter(f => f.show_chip)" :key="f.id" class="fav-chip-group">
        <button class="fav-chip-start" @click="applyFavAsFrom(f)" :title="`Als Start: ${f.address || f.label}`">↑</button>
        <button class="fav-chip-end" @click="applyFav(f)" :title="`In fokussiertes Feld einfügen: ${f.address || f.label}`">
          ⭐ <span>{{ f.label }}</span>
        </button>
      </div>
    </div>

    <!-- Favorit speichern Panel -->
    <div v-if="saveFavFor" class="save-fav-panel">
      <p class="sfp-title">Als Favorit speichern</p>
      <div class="sfp-options">
        <button :class="['sfp-opt', { active: saveFavMode === 'home' }]" @click="saveFavMode = 'home'">
          🏠 Zuhause
        </button>
        <button :class="['sfp-opt', { active: saveFavMode === 'work' }]" @click="saveFavMode = 'work'">
          💼 Arbeit
        </button>
        <button :class="['sfp-opt', { active: saveFavMode === 'custom' }]" @click="saveFavMode = 'custom'">
          ⭐ Eigener Name
        </button>
      </div>
      <input
        v-if="saveFavMode === 'custom'"
        v-model="saveFavLabel"
        class="sfp-input"
        placeholder="Name für diesen Ort"
        @keydown.enter.prevent="commitSaveFav"
      />
      <div class="sfp-actions">
        <button class="sfp-cancel" @click="closeSaveFav">Abbrechen</button>
        <button class="sfp-save" :disabled="!saveFavMode || (saveFavMode === 'custom' && !saveFavLabel.trim())" @click="commitSaveFav">
          Speichern
        </button>
      </div>
    </div>

    <!-- Routing-Modus -->
    <div class="routing-modes">
      <button
        v-for="m in routingModes"
        :key="m.value"
        class="mode-btn"
        :class="{ active: (prefStore.data.routing_mode ?? 'fastest') === m.value }"
        @click="prefStore.set('routing_mode', m.value)"
        :title="m.label"
      >{{ m.icon }} <span class="mode-label">{{ m.label }}</span></button>
    </div>

    <!-- Profil + Route-Button -->
    <div class="controls">
      <select v-model="profileSelection" class="profile-select">
        <option v-for="p in profileOptions" :key="p.value" :value="p.value">{{ p.label }}</option>
      </select>
      <button
        class="route-btn"
        :disabled="!store.origin || !store.destination || hasUnlockedWaypoints || store.isLoading"
        :title="!store.origin || !store.destination ? 'Bitte Start und Ziel aus den Vorschlägen wählen' : hasUnlockedWaypoints ? 'Bitte alle Zwischenziele aus den Vorschlägen wählen' : ''"
        @click="calculateRoute"
      >
        {{ store.isLoading ? "Berechne…" : "Route" }}
      </button>
    </div>

    <p v-if="store.error" class="error">{{ store.error }}</p>
    </div><!-- /panel-content -->
  </div>
</template>

<style scoped>
.search-panel {
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  max-width: 440px;
  background: var(--bg);
  border-radius: 14px;
  padding: 12px;
  box-shadow: var(--shadow-md);
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.input-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.icon-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 6px 4px;
  flex-shrink: 0;
  line-height: 1;
}

.autocomplete {
  position: relative;
  flex: 1;
}

.input-wrap {
  display: flex;
  align-items: center;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg-input);
  transition: border-color 0.15s;
}

.input-wrap:focus-within {
  border-color: var(--accent);
}

.input-wrap.locked {
  border-color: #22c55e;
  background: var(--bg-success);
}

.input-wrap.error {
  border-color: #f87171;
}

input {
  flex: 1;
  padding: 8px 4px;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--text-1);
  outline: none;
  min-width: 0;
}

input::placeholder {
  color: var(--text-4);
}

.spinner {
  padding: 0 8px;
  color: var(--text-4);
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }

.star-btn {
  padding: 0 6px;
  background: none;
  border: none;
  font-size: 15px;
  cursor: pointer;
  color: var(--border-2);
  line-height: 1;
  flex-shrink: 0;
  transition: color 0.15s;
}

.star-btn:not(:disabled):hover,
.star-btn.saved {
  color: #f59e0b;
}

.star-btn:disabled {
  opacity: 0.25;
  cursor: default;
}

.clear-btn {
  padding: 0 10px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  color: var(--text-4);
  line-height: 1;
  flex-shrink: 0;
  transition: color 0.15s;
}

.clear-btn:hover {
  color: #ef4444;
}

.field-error {
  margin: 2px 0 0;
  font-size: 11px;
  color: #ef4444;
}

.dropdown {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  background: var(--bg);
  border: 1px solid var(--border-1);
  border-radius: 10px;
  list-style: none;
  margin: 0;
  padding: 4px 0;
  box-shadow: var(--shadow-md);
  z-index: 30;
  max-height: 220px;
  overflow-y: auto;
}

.dropdown li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-2);
}

.dropdown li:hover,
.dropdown li.first {
  background: var(--accent-bg);
}

.dropdown li.first {
  font-weight: 500;
}

.poi-icon {
  flex-shrink: 0;
  font-size: 14px;
}

/* ── Favorites quick row ─────────────────────────────────────────────── */
.fav-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.fav-chip-group {
  display: inline-flex;
  align-items: stretch;
  border: 1px solid var(--border-2);
  border-radius: 99px;
  background: var(--bg-3);
  overflow: hidden;
  transition: border-color 0.15s;
  max-width: 180px;
  height: 30px;
}

.fav-chip-group:hover {
  border-color: var(--accent-border);
}

.fav-chip-start {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  padding: 0 8px;
  background: var(--accent-bg-2);
  border: none;
  border-right: 1px solid var(--accent-border);
  color: var(--accent-text);
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.fav-chip-start:hover {
  background: var(--accent);
  color: white;
}

.fav-chip-end {
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 12px 0 8px;
  background: transparent;
  border: none;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.fav-chip-end span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.fav-chip-end:hover {
  background: var(--accent-bg);
  color: var(--accent-text);
}

/* ── Save-Fav Panel ──────────────────────────────────────────────────── */
.save-fav-panel {
  background: var(--bg-2);
  border: 1px solid var(--border-1);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sfp-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}

.sfp-options {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.sfp-opt {
  padding: 5px 10px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  transition: all 0.15s;
}

.sfp-opt:hover {
  border-color: var(--accent);
  color: var(--accent-dark);
}

.sfp-opt.active {
  border-color: var(--accent);
  background: var(--accent-bg);
  color: var(--accent-text);
}

.sfp-input {
  padding: 6px 10px;
  border: 1px solid var(--border-2);
  border-radius: 7px;
  font-size: 13px;
  color: var(--text-1);
  outline: none;
  background: var(--bg-input);
}

.sfp-input:focus {
  border-color: var(--accent);
}

.sfp-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.sfp-cancel {
  padding: 5px 12px;
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 7px;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
}

.sfp-save {
  padding: 5px 12px;
  background: var(--accent);
  border: none;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  cursor: pointer;
}

.sfp-save:disabled {
  background: var(--border-2);
  cursor: not-allowed;
}

/* ── Controls ────────────────────────────────────────────────────────── */
.controls {
  display: flex;
  gap: 8px;
}

.profile-select {
  flex: 1;
  padding: 8px 10px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-1);
  background: var(--bg-input);
  cursor: pointer;
  outline: none;
}

.profile-select:focus {
  border-color: var(--accent);
}

.route-btn {
  padding: 8px 20px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.route-btn:hover:not(:disabled) {
  background: var(--accent-dark);
}

.route-btn:disabled {
  background: var(--border-2);
  color: var(--text-4);
  cursor: not-allowed;
}

.error {
  margin: 0;
  font-size: 12px;
  color: #ef4444;
  text-align: center;
}

/* ── Waypoints ───────────────────────────────────────────────────────── */
.wp-dot {
  font-size: 12px;
  color: var(--text-3);
  cursor: default;
}

.grip-handle {
  color: var(--text-4);
  cursor: grab;
  touch-action: none;
  user-select: none;
  padding: 0 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.grip-handle:hover { color: var(--text-2); }
.grip-handle:active { cursor: grabbing; }

.wp-drag-source {
  opacity: 0.45;
}
.wp-drag-over {
  outline: 2px solid var(--accent);
  border-radius: 10px;
  outline-offset: -1px;
}

.add-via-btn {
  padding: 3px 10px;
  border: 1.5px dashed var(--border-2);
  border-radius: 99px;
  background: none;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.add-via-btn:hover {
  border-color: var(--accent);
  color: var(--accent-dark);
}

/* ── Collapsible panel ───────────────────────────────────────────────── */
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.search-panel--collapsed .panel-header {
  margin-bottom: 0;
}

.panel-toggle {
  width: 36px;
  height: 36px;
  border: 1.5px solid var(--border-2);
  border-radius: 10px;
  background: var(--bg);
  color: var(--text-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s;
}
.panel-toggle:hover { border-color: var(--accent); color: var(--accent); }

.panel-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  flex: 1;
}

.ai-btn {
  width: 32px;
  height: 32px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
  line-height: 1;
}
.ai-btn:hover { border-color: var(--accent); background: var(--accent-bg); }
.ai-btn.active { border-color: var(--accent); background: var(--accent-bg); }

.settings-btn {
  margin-left: auto;
  width: 32px;
  height: 32px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s;
}
.settings-btn:hover { border-color: var(--accent); color: var(--accent); }

.search-panel--collapsed {
  padding: 6px;
  gap: 0;
}

.panel-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── Swap button ─────────────────────────────────────────────────────── */
.swap-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -2px 0;
  padding-left: 4px;
}

.swap-btn {
  width: 26px;
  height: 26px;
  border: 1.5px solid var(--border-2);
  border-radius: 50%;
  background: var(--bg);
  color: var(--text-3);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.swap-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-bg);
}

/* ── Routing modes ───────────────────────────────────────────────────── */
.routing-modes {
  display: flex;
  gap: 5px;
}

.mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 5px 4px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-3);
  font-size: 16px;
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1;
}

.mode-label {
  font-size: 9px;
  font-weight: 500;
  color: var(--text-3);
  white-space: nowrap;
}

.mode-btn:hover {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.mode-btn:hover .mode-label {
  color: var(--accent-text);
}

.mode-btn.active {
  border-color: var(--accent);
  background: var(--accent-bg);
  color: var(--accent-text);
}

.mode-btn.active .mode-label {
  color: var(--accent-text);
  font-weight: 600;
}
</style>
