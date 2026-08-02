type PositionCallback = (lat: number, lon: number, speed: number, heading: number, source: string) => void;

const wsBase = (import.meta.env.VITE_BACKEND_URL || "").replace(/^https?/, (m) =>
  m === "https" ? "wss" : "ws"
);

let ws: WebSocket | null = null;
let cb: PositionCallback | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let active = false;

function connect() {
  if (!active || !cb) return;
  ws = new WebSocket(`${wsBase}/ws/gps`);
  ws.onopen = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.ping || d.lat === undefined) return;
      cb?.(d.lat, d.lon, d.speed ?? 0, d.heading ?? 0, d.source ?? "server");
    } catch {
      // ignore malformed messages
    }
  };
  ws.onclose = () => {
    if (active) reconnectTimer = setTimeout(connect, 3000);
  };
  ws.onerror = () => ws?.close();
}

export function startServerGps(callback: PositionCallback) {
  cb = callback;
  active = true;
  connect();
}

export function stopServerGps() {
  active = false;
  cb = null;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  ws?.close();
  ws = null;
}
