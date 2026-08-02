<script setup lang="ts">
import { onMounted, onBeforeUnmount, watch, useTemplateRef, ref, computed } from "vue";
import { Map, GeoJSONSource, Marker, LngLatBounds, Popup, type StyleSpecification } from "maplibre-gl";
import { useMapStore } from "../stores/map";
import { useStationsStore } from "../stores/stations";
import { useAddonsStore } from "../stores/addons";
import { usePreferencesStore } from "../stores/preferences";
import { useThemeStore } from "../stores/theme";
import * as navSocket from "../services/navSocket";
import * as gpsSocket from "../services/gpsSocket";
import * as gpsSimulator from "../services/gpsSimulator";
import * as routing from "../services/routing";
import { speak } from "../services/tts";
import { useDraggable } from "../composables/useDraggable";
import { MAP_STYLES, DEFAULT_LIGHT, DEFAULT_DARK } from "../services/mapStyles";

const mapEl = useTemplateRef<HTMLDivElement>("mapEl");
const store = useMapStore();
const stationsStore = useStationsStore();
const addonsStore = useAddonsStore();
const prefStore = usePreferencesStore();
const themeStore = useThemeStore();
const backendUrl = import.meta.env.VITE_BACKEND_URL || "";
const dFuel = useDraggable("fuel-btn");

const DACH_CENTER: [number, number] = [10.45, 51.16];

let map: Map | null = null;
let gpsMarker: Marker | null = null;
let gpsMarkerEl: HTMLDivElement | null = null;
let watchId: number | null = null;
let lastManeuverDistance: number | null = null;
let waypointMarkers: Marker[] = [];
let destMarker: Marker | null = null;

// ── Map long-press context menu ──────────────────────────────────────────
interface CtxMenu { screenX: number; screenY: number; lng: number; lat: number; label: string }
const contextMenu = ref<CtxMenu | null>(null);

const ctxLeft = computed(() => {
  if (!contextMenu.value || !mapEl.value) return 0;
  return Math.min(contextMenu.value.screenX + 8, mapEl.value.clientWidth - 220);
});
const ctxTop = computed(() => {
  if (!contextMenu.value || !mapEl.value) return 0;
  return Math.min(contextMenu.value.screenY + 8, mapEl.value.clientHeight - 130);
});

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const resp = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat.toFixed(6)}&lon=${lng.toFixed(6)}&format=json&accept-language=de`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (!resp.ok) throw new Error();
    const data = await resp.json();
    const a = data.address || {};
    const road = a.road && a.house_number ? `${a.road} ${a.house_number}` : a.road;
    const city = a.city || a.town || a.village || a.hamlet;
    const parts = [road, city].filter(Boolean);
    return parts.join(", ") || data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  } catch {
    return `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  }
}

function pickMapPoint(target: "origin" | "destination" | "waypoint") {
  if (!contextMenu.value) return;
  const { lng, lat, label } = contextMenu.value;
  store.mapPickPending = { result: { label, lat, lon: lng, type: "map" }, target };
  contextMenu.value = null;
}

// ── TTS announcement flags — reset on every step change so we announce exactly
// once per distance threshold without re-triggering on GPS jitter.
let ttsAnnouncedAt300 = false;
let ttsAnnouncedNow   = false;

// Off-route detection state. Triggers a reroute once the driver has been
// more than OFF_ROUTE_THRESHOLD_M off the route for OFF_ROUTE_CONFIRMATIONS
// consecutive GPS updates. A cooldown prevents rapid back-to-back reroutes
// if the user keeps drifting after the first recalculation.
const OFF_ROUTE_THRESHOLD_M = 50;
const OFF_ROUTE_CONFIRMATIONS = 3;
const REROUTE_COOLDOWN_MS = 15_000;
let offRouteCount = 0;
let lastRerouteAt = 0;

function resolveMapStyle(): StyleSpecification {
  const isDark = themeStore.isDark;
  const id = isDark
    ? (prefStore.data.map_style_dark ?? DEFAULT_DARK)
    : (prefStore.data.map_style_light ?? DEFAULT_LIGHT);
  return (MAP_STYLES[id] ?? MAP_STYLES[isDark ? DEFAULT_DARK : DEFAULT_LIGHT]).buildStyle();
}

async function resolveStyle(): Promise<StyleSpecification> {
  return resolveMapStyle();
}

function addRouteLayers() {
  if (!map) return;
  if (!map.getSource("route")) {
    map.addSource("route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  }
  if (!map.getLayer("route-case")) {
    map.addLayer({ id: "route-case", type: "line", source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 10 } });
  }
  if (!map.getLayer("route-line")) {
    map.addLayer({ id: "route-line", type: "line", source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#3b82f6", "line-width": 6 } });
  }
}

// ── Tankstellen-Layer ────────────────────────────────────────────────────────

function addStationLayers() {
  if (!map || map.getSource("stations")) return;
  map.addSource("stations", {
    type: "geojson",
    data: { type: "FeatureCollection", features: [] },
    cluster: true,
    clusterMaxZoom: 12,
    clusterRadius: 50,
  });
  // Cluster-Kreis — Radius wächst mit der Anzahl (kein text-field, kein glyphs nötig)
  map.addLayer({
    id: "stations-cluster",
    type: "circle",
    source: "stations",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#f59e0b",
      "circle-radius": ["step", ["get", "point_count"], 16, 5, 20, 20, 25],
      "circle-stroke-width": 2,
      "circle-stroke-color": "#fff",
    },
  });
  // Einzelne Tankstelle – Kreis (grün = günstigste, gelb = offen, grau = geschlossen)
  map.addLayer({
    id: "stations-point",
    type: "circle",
    source: "stations",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "case",
        ["!", ["get", "isOpen"]], "#9ca3af",
        ["get", "isCheapest"], "#10b981",
        "#f59e0b",
      ],
      "circle-radius": 13,
      "circle-stroke-width": 2.5,
      "circle-stroke-color": "#fff",
    },
  });
}

function stationsGeoJSON(stations: typeof stationsStore.stations) {
  const cheapestId = stationsStore.cheapest?.id ?? null;
  return {
    type: "FeatureCollection" as const,
    features: stations.map((s) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.lng, s.lat] },
      properties: {
        id: s.id,
        name: s.name,
        brand: s.brand,
        street: s.street,
        place: s.place,
        isOpen: s.isOpen,
        isCheapest: s.id === cheapestId,
        e5: s.e5 || null,
        e10: s.e10 || null,
        diesel: s.diesel || null,
        price: s.price || null,
      },
    })),
  };
}

function updateStationLayer() {
  if (!map || !map.getSource("stations")) return;
  const src = map.getSource("stations") as GeoJSONSource;
  if (!stationsStore.visible || stationsStore.stations.length === 0) {
    src.setData({ type: "FeatureCollection", features: [] });
  } else {
    src.setData(stationsGeoJSON(stationsStore.stations));
  }
}

function _fmt(price: number | null | false | undefined): string {
  if (!price) return "–";
  return (price as number).toFixed(3).replace(".", ",") + " €";
}

function setupStationPopup() {
  if (!map) return;
  const popup = new Popup({ closeButton: true, maxWidth: "260px", className: "station-popup" });

  map.on("click", "stations-point", (e) => {
    const feat = e.features?.[0];
    if (!feat) return;
    const p = feat.properties as Record<string, unknown>;
    const fuel = stationsStore.activeFuel;
    const isOpen = p.isOpen as boolean;
    const isCheapest = p.isCheapest as boolean;

    const cheapestBadge = isCheapest ? '<span class="sp-badge">Günstigste ⛽</span>' : "";
    const statusBadge = isOpen
      ? '<span class="sp-open">Geöffnet</span>'
      : '<span class="sp-closed">Geschlossen</span>';

    const html = `
      <div class="sp-wrap">
        <div class="sp-header">
          <strong>${p.brand || p.name}</strong>
          ${statusBadge}
        </div>
        <div class="sp-addr">${p.street}, ${p.place}</div>
        ${cheapestBadge}
        <div class="sp-prices">
          <div class="sp-row${fuel === "e5" ? " sp-active" : ""}"><span>Super E5</span><span>${_fmt(p.e5 as number)}</span></div>
          <div class="sp-row${fuel === "e10" ? " sp-active" : ""}"><span>Super E10</span><span>${_fmt(p.e10 as number)}</span></div>
          <div class="sp-row${fuel === "diesel" ? " sp-active" : ""}"><span>Diesel</span><span>${_fmt(p.diesel as number)}</span></div>
        </div>
      </div>`;

    const coords = ((feat.geometry as unknown) as { coordinates: [number, number] }).coordinates;
    popup.setLngLat(coords).setHTML(html).addTo(map!);
  });

  map.on("mouseenter", "stations-point", () => { if (map) map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "stations-point", () => { if (map) map.getCanvas().style.cursor = ""; });
  map.on("click", "stations-cluster", (e) => {
    const feat = e.features?.[0];
    if (!feat || !map) return;
    const clusterId = feat.properties?.cluster_id as number;
    (map.getSource("stations") as GeoJSONSource).getClusterExpansionZoom(clusterId).then((zoom) => {
      if (zoom === null || zoom === undefined) return;
      const center = ((feat.geometry as unknown) as { coordinates: [number, number] }).coordinates;
      map?.easeTo({ center, zoom });
    });
  });
  map.on("mouseenter", "stations-cluster", () => { if (map) map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", "stations-cluster", () => { if (map) map.getCanvas().style.cursor = ""; });
}

function updateRoute() {
  if (!map) return;
  // Re-add layers if they got wiped (e.g. by a setStyle call)
  if (!map.getSource("route")) addRouteLayers();
  const src = map.getSource("route") as GeoJSONSource | undefined;
  if (!src) return;
  if (!store.route) {
    src.setData({ type: "FeatureCollection", features: [] });
    return;
  }
  src.setData({ type: "Feature", geometry: store.route.geometry, properties: {} });
  if (store.route.bbox && !store.isNavigating) {
    const [minLon, minLat, maxLon, maxLat] = store.route.bbox;
    map.fitBounds(new LngLatBounds([minLon, minLat], [maxLon, maxLat]), { padding: 60 });
  }
}

function updateWaypointMarkers() {
  waypointMarkers.forEach(m => m.remove());
  waypointMarkers = [];
  destMarker?.remove();
  destMarker = null;
  if (!map) return;

  store.waypoints.forEach((wp, i) => {
    if (!wp.lat || !wp.lon) return;
    const el = document.createElement("div");
    el.className = "wp-pin";
    el.textContent = String(i + 1);
    waypointMarkers.push(
      new Marker({ element: el, anchor: "bottom" }).setLngLat([wp.lon, wp.lat]).addTo(map!)
    );
  });

  if (store.destination?.lat && store.destination?.lon) {
    const el = document.createElement("div");
    el.className = "dest-flag-marker";
    el.textContent = "🏁";
    destMarker = new Marker({ element: el, anchor: "bottom" })
      .setLngLat([store.destination.lon, store.destination.lat])
      .addTo(map!);
  }
}

// Linear easing for constant-speed camera follow (no ease-in/out lurch)
const linearEase = (t: number) => t;

// How long the camera transition lasts. Slightly longer than the simulator
// tick (100 ms) so there is always a running animation — the new easeTo call
// starts from the current mid-animation position and continues smoothly.
const FOLLOW_DURATION = 150;

function onPosition(longitude: number, latitude: number, speedKmh: number, heading: number) {
  store.userPosition = [longitude, latitude];
  store.currentSpeed = speedKmh;
  store.currentHeading = heading;

  if (!gpsMarker) {
    const el = document.createElement("div");
    el.className = "gps-dot";
    gpsMarkerEl = el;
    gpsMarker = new Marker({ element: el, anchor: "center" }).setLngLat([longitude, latitude]).addTo(map!);
    const wrapper = el.parentElement;
    if (wrapper) wrapper.style.transition = `transform ${FOLLOW_DURATION}ms linear`;
  } else {
    gpsMarker.setLngLat([longitude, latitude]);
  }

  if (store.isNavigating) {
    navSocket.sendPosition(latitude, longitude, speedKmh, heading);

    if (store.followUser) {
      const bearing = store.mapBearingMode === "heading" ? heading : 0;
      map?.easeTo({
        center: [longitude, latitude],
        zoom: 17,
        bearing,
        pitch: store.mapPitch,
        duration: FOLLOW_DURATION,
        easing: linearEase,
        // Do NOT set essential:true — on iOS Safari that flag prevents touch
        // events from interrupting the animation, blocking map pan/zoom.
      });
    }

    const inst = store.activeInstruction;
    if (inst?.coordinate) {
      // For the begin step (step 0, sign=0) the coordinate is the origin —
      // the user is already there, so d ≈ 0 would fire immediately.
      // Check proximity to the *next* instruction's coordinate instead (end
      // of the first segment / destination for 2-instruction routes).
      let checkCoord = inst.coordinate;
      if (store.currentStep === 0 && inst.sign === 0 && store.route) {
        const nextCoord = store.route.instructions[1]?.coordinate;
        if (nextCoord) checkCoord = nextCoord;
      }
      const [iLat, iLon] = checkCoord;
      const dLat = (latitude - iLat) * 111_000;
      const dLon = (longitude - iLon) * 111_000 * Math.cos((latitude * Math.PI) / 180);
      const d = Math.sqrt(dLat * dLat + dLon * dLon);
      // Advance only when the user has actually passed the maneuver point:
      // either very close (<12 m) or moving away from it (lastDistance was smaller).
      if ((lastManeuverDistance !== null && d < 12) || (lastManeuverDistance !== null && d > lastManeuverDistance + 3 && lastManeuverDistance < 40)) {
        store.advanceStep();
        lastManeuverDistance = null;
      } else {
        lastManeuverDistance = d;
      }
    }

    // TTS distance announcements — use distanceToNextTurn (same value shown in
    // DrivingOverlay) so the spoken distance matches the displayed distance.
    const ttsInst = store.nextTurnInstruction;
    const ttsDist = store.distanceToNextTurn;
    if (ttsInst) {
      if (ttsDist < 320 && ttsDist > 180 && !ttsAnnouncedAt300) {
        ttsAnnouncedAt300 = true;
        speak(`In 300 Metern ${ttsInst.text}`);
      } else if (ttsDist < 60 && !ttsAnnouncedNow) {
        ttsAnnouncedNow = true;
        speak(ttsInst.text);
      }
    }

    // Off-route detection: trigger a reroute once the driver has been clearly
    // off the route for several GPS ticks in a row. Skipped while a reroute
    // is in flight or during the cooldown window after a previous one.
    if (store.distanceToRoute > OFF_ROUTE_THRESHOLD_M) {
      offRouteCount++;
    } else {
      offRouteCount = 0;
    }
    if (
      offRouteCount >= OFF_ROUTE_CONFIRMATIONS &&
      !store.isRerouting &&
      Date.now() - lastRerouteAt > REROUTE_COOLDOWN_MS
    ) {
      offRouteCount = 0;
      lastRerouteAt = Date.now();
      store.isRerouting = true;
      store.rerouteError = null;
      routing.reroute(latitude, longitude)
        .catch((e) => { store.rerouteError = e instanceof Error ? e.message : String(e); })
        .finally(() => { store.isRerouting = false; });
    }
  }
}

function startBrowserGps() {
  if (!("geolocation" in navigator)) return;
  watchId = navigator.geolocation.watchPosition(
    (pos) => {
      const { longitude, latitude } = pos.coords;
      onPosition(longitude, latitude, (pos.coords.speed ?? 0) * 3.6, pos.coords.heading ?? 0);
    },
    undefined,
    { enableHighAccuracy: true, maximumAge: 2000 }
  );
}

function stopBrowserGps() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
}

function applyGpsSource() {
  stopBrowserGps();
  gpsSocket.stopServerGps();
  gpsSimulator.stopSimulator();

  if (store.gpsSource === "browser") {
    startBrowserGps();
  } else if (store.gpsSource === "simulate") {
    if (store.route) {
      gpsSimulator.startSimulator(
        store.route.geometry.coordinates,
        (lon, lat, speed, heading) => onPosition(lon, lat, speed, heading),
        store.buildSimulatorSpeeds(),
        () => store.simulatorMultiplier,
      );
    }
  } else {
    gpsSocket.startServerGps((lat, lon, speed, heading) =>
      onPosition(lon, lat, speed, heading)
    );
  }
}

onMounted(async () => {
  if (!mapEl.value) return;
  const style = await resolveStyle();
  map = new Map({
    container: mapEl.value,
    style,
    center: DACH_CENTER,
    zoom: 6,
    fadeDuration: 0,            // no fade-in animation on tiles — feels snappier
    refreshExpiredTiles: false, // don't re-fetch cached tiles
    maxTileCacheSize: 200,      // default ~50 — keep more recent tiles in memory
  });
  // style.load fires on initial load AND after every setStyle() call —
  // re-add all custom sources/layers so they survive a theme switch.
  map.on("style.load", () => {
    addRouteLayers();
    updateRoute();
    updateWaypointMarkers();
    try {
      addStationLayers();
      updateStationLayer();
    } catch (e) {
      console.warn("[map] addStationLayers error:", e);
    }
  });

  // load fires only once — register popup handlers and restore preferences here.
  map.on("load", () => {
    setupStationPopup();
    stationsStore.setVisible(prefStore.data.stations_enabled ?? false);
  });

  // Manual map interaction during navigation breaks the auto-follow lock.
  // `originalEvent` is only present for user-initiated gestures — programmatic
  // easeTo() calls don't set it, so we don't disable follow on our own moves.
  const onUserInteract = (e: { originalEvent?: unknown }) => {
    if (!e.originalEvent || !store.isNavigating) return;
    store.followUser = false;
  };
  map.on("dragstart", onUserInteract);
  map.on("zoomstart", onUserInteract);
  map.on("rotatestart", onUserInteract);
  map.on("pitchstart", onUserInteract);
  map.on("moveend", () => {
    if (!map) return;
    const c = map.getCenter();
    store.mapCenter = [c.lng, c.lat];
  });

  // ── Long-press to pick a coordinate (desktop: mouse, mobile: touch) ──────
  let lpTimer: ReturnType<typeof setTimeout> | null = null;
  let lpStart: { x: number; y: number } | null = null;
  let lpFired = false;
  const LP_THRESHOLD = 10;
  const LP_DELAY = 1000;

  const clearLp = () => { if (lpTimer) { clearTimeout(lpTimer); lpTimer = null; } lpStart = null; };

  map.on("mousedown", (e) => {
    // Ignore if a station popup click triggered this
    if ((e.originalEvent.target as HTMLElement).closest(".maplibregl-popup")) return;
    lpStart = { x: e.point.x, y: e.point.y };
    lpTimer = setTimeout(async () => {
      lpTimer = null;
      lpFired = true;
      const { lng, lat } = e.lngLat;
      const label = await reverseGeocode(lat, lng);
      contextMenu.value = { screenX: e.point.x, screenY: e.point.y, lng, lat, label };
    }, LP_DELAY);
  });
  map.on("mousemove", (e) => {
    if (!lpTimer || !lpStart) return;
    const dx = e.point.x - lpStart.x;
    const dy = e.point.y - lpStart.y;
    if (Math.sqrt(dx * dx + dy * dy) > LP_THRESHOLD) clearLp();
  });
  map.on("mouseup", clearLp);
  // Suppress the click that fires after a long-press mouseup so the menu stays open
  map.on("click", () => { if (lpFired) { lpFired = false; return; } contextMenu.value = null; });

  // Touch long-press (mobile)
  const canvas = map.getCanvas();
  canvas.addEventListener("touchstart", (e: TouchEvent) => {
    if (e.touches.length !== 1) return;
    const t = e.touches[0];
    lpStart = { x: t.clientX, y: t.clientY };
    lpTimer = setTimeout(async () => {
      lpTimer = null;
      lpFired = true;
      if (!map || !mapEl.value) return;
      const rect = mapEl.value.getBoundingClientRect();
      const px = lpStart!.x - rect.left;
      const py = lpStart!.y - rect.top;
      const lngLat = map.unproject([px, py]);
      const label = await reverseGeocode(lngLat.lat, lngLat.lng);
      contextMenu.value = { screenX: px, screenY: py, lng: lngLat.lng, lat: lngLat.lat, label };
    }, LP_DELAY);
  }, { passive: true });
  canvas.addEventListener("touchmove", (e: TouchEvent) => {
    if (!lpTimer || !lpStart || e.touches.length !== 1) return;
    const t = e.touches[0];
    if (Math.sqrt((t.clientX - lpStart.x) ** 2 + (t.clientY - lpStart.y) ** 2) > LP_THRESHOLD) clearLp();
  }, { passive: true });
  // Only cancel the timer on touchend; don't close the menu if long-press already fired
  canvas.addEventListener("touchend", () => { if (!lpFired) clearLp(); }, { passive: true });

  applyGpsSource();
});

// Recenter on demand: when the driver taps the recenter button we flip
// followUser back to true and snap the camera onto the current position.
watch(() => store.followUser, (follow) => {
  if (follow && store.isNavigating && store.userPosition) {
    const [lon, lat] = store.userPosition;
    map?.easeTo({
      center: [lon, lat],
      zoom: 17,
      bearing: store.mapBearingMode === "heading" ? store.currentHeading : 0,
      pitch: store.mapPitch,
      duration: 500,
    });
  }
});


watch(() => store.gpsSource, applyGpsSource);

watch(() => store.route, () => {
  updateRoute();
  if (store.gpsSource === "simulate") applyGpsSource();
});

watch(
  [() => store.waypoints, () => store.destination],
  () => { if (map?.loaded()) updateWaypointMarkers(); },
  { deep: true },
);

watch(() => store.isNavigating, (navigating) => {
  if (gpsMarkerEl) {
    gpsMarkerEl.className = "gps-dot";
  }
  if (navigating) {
    navSocket.enable();
    navSocket.sendStatus(true, {
      destination: store.destination?.label,
      distanceRemaining: store.route?.distance,
      durationRemaining: store.route?.duration,
    });
    // Restart simulator from coords[0] so the user starts at the origin
    if (store.gpsSource === "simulate") applyGpsSource();
    // Snap into driving view
    const pos = store.userPosition;
    if (pos) {
      map?.easeTo({
        center: pos,
        zoom: 17,
        bearing: store.mapBearingMode === "heading" ? store.currentHeading : 0,
        pitch: store.mapPitch,
        duration: 800,
      });
    }
  } else {
    navSocket.sendStatus(false);
    navSocket.disable();
    // Return to overview
    map?.easeTo({ pitch: 0, bearing: 0, zoom: 12, duration: 800 });
    if (store.route?.bbox) {
      const [minLon, minLat, maxLon, maxLat] = store.route.bbox;
      setTimeout(() => {
        map?.fitBounds(new LngLatBounds([minLon, minLat], [maxLon, maxLat]), { padding: 60, duration: 600 });
      }, 100);
    }
  }
});

// React to pitch/bearing mode changes
watch(() => store.mapPitch, (pitch) => {
  if (store.isNavigating) {
    map?.easeTo({ pitch, duration: 500 });
  }
});

watch(() => store.mapBearingMode, (mode) => {
  if (store.isNavigating) {
    const bearing = mode === "heading" ? store.currentHeading : 0;
    map?.easeTo({ bearing, duration: 500 });
  }
});

watch(() => store.zoomToUserLocationCount, () => {
  if (!store.userPosition || !map) return;
  const [lon, lat] = store.userPosition;
  // 200 m radius as a bounding box
  const dLat = 200 / 111_000;
  const dLon = 200 / (111_000 * Math.cos((lat * Math.PI) / 180));
  map.fitBounds(
    new LngLatBounds([lon - dLon, lat - dLat], [lon + dLon, lat + dLat]),
    { padding: 40, duration: 600, pitch: 0, bearing: 0 },
  );
});

// Tankstellen: Layer bei Sichtbarkeits- oder Datenänderung neu rendern
watch([() => stationsStore.visible, () => stationsStore.stations], () => {
  if (map?.loaded()) updateStationLayer();
});

// Tankstellen laden wenn Layer eingeblendet wird
watch(() => stationsStore.visible, async (visible) => {
  if (!visible) return;
  if (store.isNavigating && store.route) {
    await stationsStore.fetchAlongRoute(store.route.geometry.coordinates);
  } else if (store.userPosition) {
    const [lon, lat] = store.userPosition;
    await stationsStore.fetchNearby(lat, lon);
  }
});

// Beim Routenwechsel Tankstellen neu laden (wenn sichtbar + navigierend)
watch(() => store.route, async (route) => {
  if (!stationsStore.visible || !route) return;
  await stationsStore.fetchAlongRoute(route.geometry.coordinates);
});

watch(() => store.currentStep, () => {
  lastManeuverDistance = null;
  ttsAnnouncedAt300 = false;
  ttsAnnouncedNow   = false;
  const inst = store.activeInstruction;
  const pos = store.userPosition;
  if (inst && store.isNavigating) {
    // Immediately announce destination / via-point reached
    if (inst.sign === 4) speak("Sie haben Ihr Ziel erreicht");
    else if (inst.sign === 5) speak("Zwischenziel erreicht");
    navSocket.sendInstruction(inst.text, inst.distance, inst.sign, inst.street);
    navSocket.sendStatus(true, {
      lat: pos?.[1], lon: pos?.[0],
      instruction: inst.text,
      distanceRemaining: store.remainingDistance,
    });
  }
});

// Update map style when theme or user style preference changes.
watch(
  [() => themeStore.isDark, () => prefStore.data.map_style_light, () => prefStore.data.map_style_dark],
  () => { map?.setStyle(resolveMapStyle()); },
);

// Track Recorder: draw/remove a saved track on the map
watch(() => store.displayedTrack, (geojson) => {
  if (!map) return;
  const src = map.getSource("track-display") as GeoJSONSource | undefined;
  if (!geojson) {
    if (src) {
      (src as GeoJSONSource).setData({ type: "FeatureCollection", features: [] });
      map.setLayoutProperty("track-display-line", "visibility", "none");
    }
    return;
  }
  if (!src) {
    map.addSource("track-display", { type: "geojson", data: geojson as GeoJSON.Feature });
    map.addLayer({
      id: "track-display-line",
      type: "line",
      source: "track-display",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#7c3aed", "line-width": 4, "line-opacity": 0.85 },
    });
  } else {
    src.setData(geojson as GeoJSON.Feature);
    map.setLayoutProperty("track-display-line", "visibility", "visible");
  }
  // Fit map to track bounds
  const coords = (geojson as any).geometry?.coordinates as [number, number][];
  if (coords?.length > 1) {
    const bounds = coords.reduce(
      (b, c) => b.extend(c),
      new LngLatBounds(coords[0], coords[0]),
    );
    map.fitBounds(bounds, { padding: 60, duration: 600 });
  }
});

onBeforeUnmount(() => {
  stopBrowserGps();
  gpsSocket.stopServerGps();
  gpsSimulator.stopSimulator();
  navSocket.disable();
  gpsMarker?.remove();
  waypointMarkers.forEach(m => m.remove());
  destMarker?.remove();
  map?.remove();
  map = null;
});
</script>

<template>
  <div ref="mapEl" class="map" />

  <!-- Long-press context menu -->
  <Teleport to="body">
    <div
      v-if="contextMenu"
      class="map-ctx-menu"
      :style="{ left: ctxLeft + 'px', top: ctxTop + 'px' }"
    >
      <p class="ctx-addr">{{ contextMenu.label }}</p>
      <div class="ctx-actions">
        <button @click="pickMapPoint('origin')">↑ Start</button>
        <button @click="pickMapPoint('destination')">🏁 Ziel</button>
        <button @click="pickMapPoint('waypoint')">+ Via</button>
      </div>
      <button class="ctx-close" @click="contextMenu = null">✕</button>
    </div>
  </Teleport>

  <!-- REC-Indikator: erscheint wenn Track Recorder aktiv aufzeichnet -->
  <div v-if="addonsStore.trackRecorderActive && addonsStore.isInstalled('track_recorder')" class="rec-badge">
    <span class="rec-dot"></span>
    REC
    <span v-if="addonsStore.trackRecorderStats">
      · {{ addonsStore.trackRecorderStats.distance_km.toFixed(2) }} km
    </span>
  </div>

  <!-- Track-Display-Chip: erscheint wenn ein gespeicherter Track auf der Karte liegt -->
  <button
    v-if="store.displayedTrack"
    class="track-clear-chip"
    title="Track ausblenden"
    @click="store.clearDisplayedTrack()"
  >
    🗺 Track ausblenden ✕
  </button>

  <!-- ⛽ Tankstellen-Toggle (nur wenn Tankerkönig-Add-on installiert) -->
  <button
    v-if="!store.isNavigating && addonsStore.isInstalled('tankerkoenig')"
    class="fuel-btn"
    :class="{ active: stationsStore.visible, loading: stationsStore.loading, dragging: dFuel.active.value }"
    :style="dFuel.style.value"
    :title="stationsStore.visible ? 'Tankstellen ausblenden' : 'Tankstellen anzeigen'"
    @pointerdown="dFuel.onPointerDown"
    @pointermove="dFuel.onPointerMove"
    @pointerup="dFuel.onPointerUp"
    @pointercancel="dFuel.onPointerCancel"
    @click.capture="dFuel.guardClick"
    @click="stationsStore.toggle()"
  >
    ⛽
  </button>
</template>

<style scoped>
.map {
  position: absolute;
  inset: 0;
}

.rec-badge {
  position: absolute;
  bottom: 100px;
  left: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  background: rgba(0,0,0,0.65);
  color: white;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  pointer-events: none;
}

.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
  animation: rec-pulse 1.2s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes rec-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.track-clear-chip {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  padding: 6px 14px;
  background: #7c3aed;
  color: white;
  border: none;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  white-space: nowrap;
}
.track-clear-chip:hover { background: #6d28d9; }

.fuel-btn {
  position: absolute;
  bottom: 140px;
  right: 12px;
  z-index: 10;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 12px;
  background: var(--bg);
  box-shadow: var(--shadow-sm);
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, transform 0.15s;
  touch-action: none;
}

.fuel-btn.dragging {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  cursor: grabbing;
  opacity: 0.9;
  z-index: 30;
}
.fuel-btn.active {
  background: var(--accent);
}
.fuel-btn.loading {
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

:global(.gps-dot) {
  width: 20px;
  height: 20px;
  background: #3b82f6;
  border: 3px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.3), 0 2px 6px rgba(0,0,0,0.3);
}

:global(.wp-pin) {
  min-width: 24px;
  height: 24px;
  padding: 0 5px;
  background: #f97316;
  border: 2.5px solid white;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 700;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.35);
  pointer-events: none;
  position: relative;
}
:global(.wp-pin::after) {
  content: "";
  position: absolute;
  bottom: -7px;
  left: 50%;
  transform: translateX(-50%);
  border: 5px solid transparent;
  border-top: 7px solid #f97316;
}

:global(.dest-flag-marker) {
  font-size: 24px;
  line-height: 1;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.45));
  pointer-events: none;
}


/* Tankstellen-Popup Styles */
:global(.station-popup .maplibregl-popup-content) {
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 24px rgba(0,0,0,0.2);
  font-family: system-ui, -apple-system, sans-serif;
}
:global(.sp-wrap) { font-size: 13px; }
:global(.sp-header) {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px 6px; gap: 8px;
  background: #f9fafb; border-bottom: 1px solid #e5e7eb;
}
:global(.sp-header strong) { font-size: 14px; color: #111827; }
:global(.sp-open)   { font-size: 11px; color: #10b981; font-weight: 600; white-space: nowrap; }
:global(.sp-closed) { font-size: 11px; color: #9ca3af; font-weight: 600; white-space: nowrap; }
:global(.sp-addr)   { padding: 4px 12px; font-size: 11px; color: #6b7280; }
:global(.sp-badge)  {
  margin: 2px 12px 4px; display: inline-block;
  font-size: 11px; font-weight: 600; color: #059669;
  background: #d1fae5; border-radius: 99px; padding: 1px 8px;
}
:global(.sp-prices) { padding: 6px 12px 10px; display: flex; flex-direction: column; gap: 4px; }
:global(.sp-row)    { display: flex; justify-content: space-between; color: #374151; }
:global(.sp-row.sp-active) { font-weight: 700; color: #111827; }

/* Map long-press context menu — global because it's teleported to body */
:global(.map-ctx-menu) {
  position: fixed;
  z-index: 9999;
  background: var(--bg, #fff);
  border: 1px solid var(--border-1, #e5e7eb);
  border-radius: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  padding: 10px 12px 8px;
  min-width: 200px;
  max-width: 260px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
:global(.ctx-addr) {
  font-size: 12px;
  color: var(--text-2, #6b7280);
  margin: 0;
  line-height: 1.4;
  word-break: break-word;
}
:global(.ctx-actions) {
  display: flex;
  gap: 6px;
}
:global(.ctx-actions button) {
  flex: 1;
  padding: 6px 4px;
  border: 1px solid var(--border-1, #e5e7eb);
  border-radius: 8px;
  background: var(--bg-2, #f9fafb);
  color: var(--text-1, #111827);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.12s;
}
:global(.ctx-actions button:hover) {
  background: var(--accent-bg, #eff6ff);
  border-color: var(--accent, #3b82f6);
  color: var(--accent, #3b82f6);
}
:global(.ctx-close) {
  position: absolute;
  top: 6px;
  right: 8px;
  background: none;
  border: none;
  font-size: 14px;
  color: var(--text-3, #9ca3af);
  cursor: pointer;
  padding: 2px 4px;
  line-height: 1;
}
:global(.ctx-close:hover) { color: var(--text-1, #111827); }
</style>
