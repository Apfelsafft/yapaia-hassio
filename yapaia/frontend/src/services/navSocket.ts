import { useUserStore } from "../stores/user";
import { useThemeStore } from "../stores/theme";

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const _WS = _BACKEND.replace(/^https?/, (m) => (m === "https" ? "wss" : "ws"));

let _socket: WebSocket | null = null;
let _timer: ReturnType<typeof setTimeout> | null = null;
let _active = false;

function _handleCommand(data: Record<string, unknown>) {
  if (data.command === "theme") {
    const v = data.value as string;
    if (v === "dark" || v === "light") {
      useThemeStore().applyExternal(v);
    }
  }
}

function _connect() {
  if (!_active || _socket?.readyState === WebSocket.OPEN) return;
  const token = useUserStore().token;
  _socket = new WebSocket(`${_WS}/ws/navigation?token=${encodeURIComponent(token)}`);
  _socket.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "command") _handleCommand(data);
    } catch { /* ignore malformed */ }
  };
  _socket.onclose = () => {
    if (_active) _timer = setTimeout(_connect, 3000);
  };
}

function _send(data: object) {
  if (_socket?.readyState === WebSocket.OPEN) _socket.send(JSON.stringify(data));
}

export function enable() {
  _active = true;
  _connect();
}

export function disable() {
  _active = false;
  if (_timer) { clearTimeout(_timer); _timer = null; }
  _socket?.close();
  _socket = null;
}

export function sendPosition(lat: number, lon: number, speed = 0, heading = 0) {
  _send({ type: "position", lat, lon, speed, heading });
}

export function sendInstruction(text: string, distance: number, sign: number, street = "") {
  _send({ type: "instruction", text, distance, sign, street });
}

export function sendStatus(
  navigating: boolean,
  opts: {
    lat?: number; lon?: number; instruction?: string;
    distanceRemaining?: number; durationRemaining?: number; destination?: string;
  } = {}
) {
  _send({
    type: "status",
    navigating,
    lat: opts.lat,
    lon: opts.lon,
    instruction: opts.instruction,
    distance_remaining: opts.distanceRemaining,
    duration_remaining: opts.durationRemaining,
    destination: opts.destination,
  });
}
