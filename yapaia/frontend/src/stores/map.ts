import { defineStore } from "pinia";
import { ref, computed, watch } from "vue";
import { usePreferencesStore } from "./preferences";

export interface SearchResult {
  label: string;
  lat: number;
  lon: number;
  type: string;
}

export interface RouteInstruction {
  text: string;
  street: string;
  distance: number;
  duration: number;
  sign: number;
  exit_number: number;
  coordinate: [number, number] | null; // [lat, lon]
}

export interface Route {
  distance: number;
  duration: number;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  bbox: [number, number, number, number] | null;
  instructions: RouteInstruction[];
  // GraphHopper details=max_speed: [[from_pt_idx, to_pt_idx, value_kmh | null], ...]
  max_speed?: [number, number, number | null][];
}

export const useMapStore = defineStore("map", () => {
  const origin = ref<SearchResult | null>(null);
  const destination = ref<SearchResult | null>(null);
  const route = ref<Route | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const isNavigating = ref(false);
  const currentStep = ref(0);
  const userPosition = ref<[number, number] | null>(null); // [lon, lat]
  const currentSpeed = ref(0);    // km/h
  const currentHeading = ref(0);  // degrees, 0 = north
  const gpsSource = ref<"browser" | "server" | "url" | "simulate">("browser");

  // Map view settings
  const mapPitch = ref<0 | 60>(0);
  const mapBearingMode = ref<"north" | "heading">("north");
  const mapCenter = ref<[number, number]>([0, 0]); // [lon, lat], updated on moveend

  // Route panel: collapsed during navigation by default
  const isPanelExpanded = ref(true);

  // Track display (from Track Recorder addon)
  const displayedTrack = ref<object | null>(null);  // GeoJSON Feature
  function showTrackOnMap(geojson: object) { displayedTrack.value = geojson; }
  function clearDisplayedTrack() { displayedTrack.value = null; }

  // GPS Simulator: time multiplier (1 = real-time, 2 = double speed, …)
  const simulatorMultiplier = ref(1);
  const _MULTIPLIER_STEPS = [0.5, 1, 2, 5, 10];
  function stepSimulatorMultiplier(dir: 1 | -1) {
    const idx = _MULTIPLIER_STEPS.indexOf(simulatorMultiplier.value);
    const next = Math.max(0, Math.min(_MULTIPLIER_STEPS.length - 1, idx + dir));
    simulatorMultiplier.value = _MULTIPLIER_STEPS[next];
  }

  /** Pre-compute per-waypoint speed array from route.max_speed for the simulator. */
  function buildSimulatorSpeeds(): number[] {
    const r = route.value;
    if (!r) return [];
    const n = r.geometry.coordinates.length;
    const speeds = new Array<number>(n).fill(50);
    if (r.max_speed) {
      for (const [from, to, val] of r.max_speed) {
        if (val != null && val > 0) {
          for (let i = from; i <= Math.min(to, n - 1); i++) {
            speeds[i] = val;
          }
        }
      }
    }
    return speeds;
  }

  const activeInstruction = computed(() =>
    route.value?.instructions[currentStep.value] ?? null
  );

  // Distance from current GPS position to the next maneuver point (meters)
  const distanceToManeuver = computed(() => {
    const pos = userPosition.value;
    const inst = activeInstruction.value;
    if (!pos || !inst?.coordinate) return 0;
    const [uLon, uLat] = pos;
    const [iLat, iLon] = inst.coordinate;
    const dLat = (iLat - uLat) * 111_000;
    const dLon = (iLon - uLon) * 111_000 * Math.cos((uLat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon);
  });

  // For step 0 (begin, sign=0), distanceToManeuver measures distance to the
  // origin coordinate — which is ~0 because the user IS there. For the live
  // remaining-distance readout we need the distance to the END of segment 0
  // (i.e. instructions[1].coordinate) instead.
  const distanceToSegmentEnd = computed<number>(() => {
    if (!route.value || !userPosition.value) return 0;
    const k = currentStep.value;
    const instructions = route.value.instructions;
    if (k !== 0 || instructions[k]?.sign !== 0) return distanceToManeuver.value;
    const next = instructions[1];
    if (!next?.coordinate) return distanceToManeuver.value;
    const [uLon, uLat] = userPosition.value;
    const [nLat, nLon] = next.coordinate;
    const dLat = (nLat - uLat) * 111_000;
    const dLon = (nLon - uLon) * 111_000 * Math.cos((uLat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon);
  });

  const remainingDistance = computed(() => {
    if (!route.value) return 0;
    const instructions = route.value.instructions;
    const k = currentStep.value;
    // For begin step (k=0, sign=0): distanceToManeuver points to origin (~0).
    // Use distanceToSegmentEnd (dist to instructions[1].coord) instead.
    const isBeginStep = k === 0 && instructions[k]?.sign === 0;
    const toNext = isBeginStep ? distanceToSegmentEnd.value : distanceToManeuver.value;
    // Sum distances of all segments starting from the one ahead of us.
    // For begin step that is segment 1 (post-turn); for other steps it is
    // segment k (which runs FROM instructions[k].coord, i.e. after the turn).
    const startFrom = isBeginStep ? 1 : k;
    let total = toNext;
    for (let i = startFrom; i < instructions.length; i++) {
      total += instructions[i].distance;
    }
    return total;
  });

  const remainingDuration = computed(() => {
    if (!route.value) return 0;
    const instructions = route.value.instructions;
    const k = currentStep.value;
    const isBeginStep = k === 0 && instructions[k]?.sign === 0;
    const toNext = isBeginStep ? distanceToSegmentEnd.value : distanceToManeuver.value;
    // Current segment: for begin step it is seg 0; for step k it is seg k-1
    // (the segment whose end is the upcoming maneuver point).
    const curSegIdx = isBeginStep ? 0 : k - 1;
    const curSeg = curSegIdx >= 0 ? instructions[curSegIdx] : null;
    const startFrom = isBeginStep ? 1 : k;
    let total = 0;
    for (let i = startFrom; i < instructions.length; i++) {
      total += instructions[i].duration;
    }
    // Scale the current segment's duration by the fraction still ahead.
    if (curSeg && curSeg.distance > 0) {
      total += curSeg.duration * Math.min(1, Math.max(0, toNext / curSeg.distance));
    } else if (curSeg) {
      total += curSeg.duration;
    }
    return total;
  });

  // Index of next instruction with a real turn (sign != 0, i.e. not straight ahead)
  const nextTurnStep = computed(() => {
    if (!route.value) return currentStep.value;
    const instructions = route.value.instructions;
    for (let i = currentStep.value; i < instructions.length; i++) {
      if (instructions[i].sign !== 0) return i;
    }
    return instructions.length - 1;
  });

  // The upcoming turn instruction to display in the driving overlay.
  // Exception: when still on the begin step (step 0, sign=0) and the only
  // "turn" ahead is the arrival, show the begin instruction (sign=0 → ↑)
  // instead of "🏁" — the finish flag at 150m confusingly looks like arrival.
  const nextTurnInstruction = computed(() => {
    const inst = route.value?.instructions[nextTurnStep.value] ?? activeInstruction.value;
    if (
      currentStep.value === 0 &&
      activeInstruction.value?.sign === 0 &&
      inst?.sign === 4
    ) {
      return activeInstruction.value;
    }
    return inst;
  });

  // Index and instruction of the turn AFTER the next one
  const afterNextTurnStep = computed(() => {
    if (!route.value) return -1;
    const instructions = route.value.instructions;
    for (let i = nextTurnStep.value + 1; i < instructions.length; i++) {
      if (instructions[i].sign !== 0) return i;
    }
    return -1;
  });

  const afterNextTurnInstruction = computed(() =>
    afterNextTurnStep.value >= 0
      ? (route.value?.instructions[afterNextTurnStep.value] ?? null)
      : null
  );

  // Distance to next real turn from current GPS position.
  const distanceToNextTurn = computed(() => {
    if (!route.value) return distanceToManeuver.value;
    const target = nextTurnStep.value;
    const k = currentStep.value;
    if (target === k) return distanceToManeuver.value;
    const instructions = route.value.instructions;
    const isBeginStep = k === 0 && instructions[k]?.sign === 0;
    if (isBeginStep) {
      // distanceToManeuver points to origin; use dist to end of segment 0.
      let d = distanceToSegmentEnd.value;
      for (let i = 1; i < target; i++) { d += instructions[i].distance; }
      return d;
    }
    // General case: remaining in current segment + all intermediate segments.
    let d = distanceToManeuver.value;
    for (let i = k; i < target; i++) { d += instructions[i].distance; }
    return d;
  });

  // Index of the route point nearest to the user — used to look up the speed
  // limit of the segment the user is currently driving on.
  const nearestRoutePointIdx = computed(() => {
    if (!route.value || !userPosition.value) return -1;
    const coords = route.value.geometry.coordinates;
    const [uLon, uLat] = userPosition.value;
    const cosLat = Math.cos((uLat * Math.PI) / 180);
    let bestIdx = -1;
    let bestDist = Infinity;
    for (let i = 0; i < coords.length; i++) {
      const [lon, lat] = coords[i];
      const dLat = (lat - uLat) * 111_000;
      const dLon = (lon - uLon) * 111_000 * cosLat;
      const d = dLat * dLat + dLon * dLon;
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    }
    return bestIdx;
  });

  const currentSpeedLimit = computed<number | null>(() => {
    const ms = route.value?.max_speed;
    const idx = nearestRoutePointIdx.value;
    if (!ms || idx < 0) return null;
    for (const seg of ms) {
      const [from, to, val] = seg;
      if (idx >= from && idx < to && val != null) return val;
    }
    return null;
  });

  // Live distance from the user's GPS position to the closest point on the
  // active route. Used by the driving overlay's off-route detection.
  const distanceToRoute = computed(() => {
    if (!route.value || !userPosition.value) return 0;
    const idx = nearestRoutePointIdx.value;
    if (idx < 0) return 0;
    const [rLon, rLat] = route.value.geometry.coordinates[idx];
    const [uLon, uLat] = userPosition.value;
    const dLat = (rLat - uLat) * 111_000;
    const dLon = (rLon - uLon) * 111_000 * Math.cos((uLat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon);
  });

  // Off-route + reroute state. Mutated from MapView's onPosition handler.
  const isRerouting = ref(false);
  const rerouteError = ref<string | null>(null);

  // Intermediate waypoints (between origin and destination)
  const waypoints = ref<SearchResult[]>([]);

  // Set by MapView long-press; consumed by SearchBar to fill origin/destination/waypoint
  const mapPickPending = ref<{ result: SearchResult; target: "origin" | "destination" | "waypoint" } | null>(null);

  // Camera follow-mode. When the driver pans/zooms the map manually during
  // navigation we flip this to false so the map stops auto-recentering, and
  // show a "recenter" button to opt back in.
  const followUser = ref(true);

  // Navigation may only be started if either the simulator is selected (always
  // ok) or the user's current GPS position is close enough to the chosen
  // origin. Otherwise the route is shown as a preview only.
  const NAV_START_TOLERANCE_M = 200;
  const canStartNavigation = computed(() => {
    if (!route.value) return false;
    if (gpsSource.value === "simulate") return true;
    if (!userPosition.value || !origin.value) return false;
    const [uLon, uLat] = userPosition.value;
    const dLat = (origin.value.lat - uLat) * 111_000;
    const dLon = (origin.value.lon - uLon) * 111_000 * Math.cos((uLat * Math.PI) / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon) < NAV_START_TOLERANCE_M;
  });

  function setOrigin(r: SearchResult | null) { origin.value = r; }
  function setDestination(r: SearchResult | null) { destination.value = r; }

  function addWaypoint(r: SearchResult) {
    waypoints.value = [...waypoints.value, r];
  }

  function setWaypoint(idx: number, r: SearchResult) {
    const arr = [...waypoints.value];
    arr[idx] = r;
    waypoints.value = arr;
  }

  function removeWaypoint(idx: number) {
    waypoints.value = waypoints.value.filter((_, i) => i !== idx);
  }

  function clearWaypoints() {
    waypoints.value = [];
  }

  function reorderWaypoints(from: number, to: number) {
    if (from === to) return;
    const arr = [...waypoints.value];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    waypoints.value = arr;
  }

  function setRoute(r: Route) {
    route.value = r;
    // During an active navigation (rerouting), skip the "Begin" pseudo-step
    // so the driving overlay immediately reflects the first real maneuver.
    if (isNavigating.value && r.instructions.length > 2) {
      currentStep.value = 1;
    } else {
      currentStep.value = 0;
      isPanelExpanded.value = true;
    }
    error.value = null;
  }

  function clearRoute() {
    route.value = null;
    isNavigating.value = false;
    currentStep.value = 0;
  }

  function startNavigation() {
    if (route.value) {
      isNavigating.value = true;
      isPanelExpanded.value = false; // hide big panel during driving
      followUser.value = true;
      // Skip the "begin route" pseudo-instruction (coord = origin, sign = 0),
      // but only when there are real intermediate maneuvers (length > 2).
      // For 2-instruction routes (begin + arrive) jumping to step 1 would
      // immediately trigger the arrival announcement before the user moves.
      if (currentStep.value === 0 && route.value.instructions.length > 2) {
        currentStep.value = 1;
      }
    }
  }

  function stopNavigation() {
    isNavigating.value = false;
    isPanelExpanded.value = true;
  }

  function advanceStep() {
    if (route.value && currentStep.value < route.value.instructions.length - 1) {
      currentStep.value++;
    }
  }

  function toggle3D() {
    mapPitch.value = mapPitch.value === 0 ? 60 : 0;
  }

  function toggleBearingMode() {
    mapBearingMode.value = mapBearingMode.value === "north" ? "heading" : "north";
  }

  function togglePanel() {
    isPanelExpanded.value = !isPanelExpanded.value;
  }

  const zoomToUserLocationCount = ref(0);
  function zoomToUserLocation() {
    zoomToUserLocationCount.value++;
  }

  // Hydrate state from the user's saved preferences. Called by App.vue once
  // the preferences store has loaded its data. The applying flag prevents
  // the watchers below from immediately writing these values back.
  let applying = false;
  function applyPreferences(p: {
    gps_source?: "browser" | "server" | "url" | "simulate";
    map_pitch?: 0 | 60;
    map_bearing_mode?: "north" | "heading";
  }) {
    applying = true;
    if (p.gps_source) gpsSource.value = p.gps_source;
    if (p.map_pitch === 0 || p.map_pitch === 60) mapPitch.value = p.map_pitch;
    if (p.map_bearing_mode) mapBearingMode.value = p.map_bearing_mode;
    // Let Vue process the assignments, then re-enable persistence.
    queueMicrotask(() => { applying = false; });
  }

  // Persist preference-relevant changes back to the backend (debounced inside
  // the preferences store). Watchers fire AFTER applyPreferences() finishes
  // because we clear `applying` in a microtask.
  const prefs = usePreferencesStore();
  watch(gpsSource, (v) => { if (!applying) prefs.set("gps_source", v); });
  watch(mapPitch, (v) => { if (!applying) prefs.set("map_pitch", v); });
  watch(mapBearingMode, (v) => { if (!applying) prefs.set("map_bearing_mode", v); });

  return {
    origin, destination, route, isLoading, error,
    isNavigating, currentStep, userPosition, gpsSource,
    currentSpeed, currentHeading,
    mapPitch, mapBearingMode, isPanelExpanded,
    activeInstruction, remainingDistance, remainingDuration, distanceToManeuver,
    nextTurnStep, nextTurnInstruction, distanceToNextTurn,
    afterNextTurnInstruction,
    canStartNavigation, currentSpeedLimit,
    distanceToRoute, isRerouting, rerouteError,
    followUser,
    waypoints, addWaypoint, setWaypoint, removeWaypoint, clearWaypoints, reorderWaypoints,
    mapPickPending,
    applyPreferences,
    setOrigin, setDestination, setRoute, clearRoute,
    startNavigation, stopNavigation, advanceStep,
    toggle3D, toggleBearingMode, togglePanel,
    mapCenter,
    zoomToUserLocationCount, zoomToUserLocation,
    displayedTrack, showTrackOnMap, clearDisplayedTrack,
    simulatorMultiplier, stepSimulatorMultiplier, buildSimulatorSpeeds,
  };
});
