import { useMapStore } from "../stores/map";
import { useUserStore } from "../stores/user";
import { usePreferencesStore } from "../stores/preferences";
import { useVehiclesStore } from "../stores/vehicles";
import { routingUrl } from "./serviceUrl";

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

async function fetchMotorhomeDims(authHeaders: Record<string, string>) {
  try {
    const resp = await fetch(`${_BACKEND}/api/vehicles/`, { headers: authHeaders });
    if (!resp.ok) return null;
    const vehicles = await resp.json();
    const v = vehicles.find((x: { type: string }) => x.type === "motorhome");
    if (!v) return null;
    return {
      height: v.height ?? undefined,
      width: v.width ?? undefined,
      weight: v.weight ?? undefined,
    };
  } catch {
    return null;
  }
}

/**
 * Run a routing request using the current origin and destination from the
 * map store and the user's preferred profile. Throws on failure.
 */
export async function calculateRoute(): Promise<void> {
  const mapStore = useMapStore();
  const userStore = useUserStore();
  const prefStore = usePreferencesStore();
  const vehiclesStore = useVehiclesStore();

  if (!mapStore.origin || !mapStore.destination) return;

  const vid = prefStore.data.default_vehicle_id;
  const vehicle = vid ? vehiclesStore.items.find(v => v.id === vid) : null;
  const profile = vehicle ? vehicle.type : (prefStore.data.default_profile ?? "car");

  const routingMode = prefStore.data.routing_mode ?? "fastest";

  const params = new URLSearchParams({
    from_lat: String(mapStore.origin.lat),
    from_lon: String(mapStore.origin.lon),
    to_lat:   String(mapStore.destination.lat),
    to_lon:   String(mapStore.destination.lon),
    profile,
    routing_mode: routingMode,
  });

  // Append intermediate waypoints in order (only real ones with coordinates)
  for (const wp of mapStore.waypoints) {
    if (wp.lat !== 0 || wp.lon !== 0) {
      params.append("via", `${wp.lat},${wp.lon}`);
    }
  }

  if (vehicle) {
    if (vehicle.height) params.set("vehicle_height", String(vehicle.height));
    if (vehicle.width)  params.set("vehicle_width",  String(vehicle.width));
    if (vehicle.weight) params.set("vehicle_weight", String(vehicle.weight));
  } else if (profile === "motorhome") {
    const dims = await fetchMotorhomeDims(userStore.authHeaders());
    if (dims) {
      if (dims.height) params.set("vehicle_height", String(dims.height));
      if (dims.width)  params.set("vehicle_width",  String(dims.width));
      if (dims.weight) params.set("vehicle_weight", String(dims.weight));
    }
  }

  const resp = await fetch(`${routingUrl()}/api/route?${params}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  mapStore.setRoute(await resp.json());
}

/**
 * Recompute the route from the user's current GPS position to the existing
 * destination. Used when the driver has strayed off the active route.
 */
export async function reroute(lat: number, lon: number): Promise<void> {
  const mapStore = useMapStore();
  if (!mapStore.destination) return;
  // Drop intermediate waypoints when rerouting — the driver has deviated and
  // already passed (or skipped) them.
  mapStore.clearWaypoints();
  mapStore.setOrigin({ label: "Mein Standort", lat, lon, type: "gps" });
  await calculateRoute();
}
