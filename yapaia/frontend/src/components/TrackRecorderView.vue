<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useUserStore } from "../stores/user";
import { useToastsStore } from "../stores/toasts";
import { useMapStore } from "../stores/map";

const emit = defineEmits<{ (e: "close-modal"): void }>();

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const ADDON_ID = "track_recorder";

const userStore = useUserStore();
const toasts = useToastsStore();
const mapStore = useMapStore();

interface TrackSummary {
  id: string;
  start_time: string;
  end_time: string;
  distance_km: number;
  avg_speed: number;
  max_speed: number;
  point_count: number;
  locked: boolean;
}

interface ActiveStatus {
  active: boolean;
  point_count?: number;
  distance_km?: number;
  start_time?: string;
}

const tracks = ref<TrackSummary[]>([]);
const active = ref<ActiveStatus>({ active: false });
const loading = ref(false);
const notInstalled = ref(false);
const deletingId = ref<string | null>(null);
const lockingId = ref<string | null>(null);
const exportingId = ref<string | null>(null);
const showingOnMapId = ref<string | null>(null);

let pollTimer: ReturnType<typeof setInterval> | null = null;

function headers() {
  return userStore.authHeaders();
}

async function fetchTracks() {
  loading.value = true;
  try {
    const resp = await fetch(`${_BACKEND}/api/addons/${ADDON_ID}/tracks`, { headers: headers() });
    if (resp.status === 403) { notInstalled.value = true; return; }
    if (resp.ok) {
      notInstalled.value = false;
      const data = await resp.json();
      tracks.value = data.tracks;
    }
  } finally {
    loading.value = false;
  }
}

async function fetchActive() {
  try {
    const resp = await fetch(`${_BACKEND}/api/addons/${ADDON_ID}/active`, { headers: headers() });
    if (resp.status === 403) { notInstalled.value = true; return; }
    if (resp.ok) active.value = await resp.json();
  } catch { /* ignore */ }
}

async function deleteTrack(id: string) {
  deletingId.value = id;
  try {
    const resp = await fetch(`${_BACKEND}/api/addons/${ADDON_ID}/tracks/${id}`, {
      method: "DELETE",
      headers: headers(),
    });
    if (resp.ok) {
      tracks.value = tracks.value.filter((t) => t.id !== id);
      toasts.success("Track gelöscht");
    } else {
      const body = await resp.json();
      toasts.error(body.error ?? "Löschen fehlgeschlagen");
    }
  } finally {
    deletingId.value = null;
  }
}

async function toggleLock(id: string) {
  lockingId.value = id;
  try {
    const resp = await fetch(`${_BACKEND}/api/addons/${ADDON_ID}/tracks/${id}/lock`, {
      method: "PATCH",
      headers: headers(),
    });
    if (resp.ok) {
      const body = await resp.json();
      const idx = tracks.value.findIndex((t) => t.id === id);
      if (idx !== -1) tracks.value[idx] = { ...tracks.value[idx], locked: body.locked };
      toasts.success(body.locked ? "Track gesperrt" : "Sperre aufgehoben");
    }
  } finally {
    lockingId.value = null;
  }
}

async function showOnMap(id: string) {
  showingOnMapId.value = id;
  try {
    const resp = await fetch(
      `${_BACKEND}/api/addons/${ADDON_ID}/tracks/${id}/export?format=geojson`,
      { headers: headers() },
    );
    if (!resp.ok) { toasts.error("Track laden fehlgeschlagen"); return; }
    const geojson = await resp.json();
    mapStore.showTrackOnMap(geojson);
    emit("close-modal");
  } finally {
    showingOnMapId.value = null;
  }
}

function exportTrack(id: string, fmt: string) {
  exportingId.value = id;
  const url = `${_BACKEND}/api/addons/${ADDON_ID}/tracks/${id}/export?format=${fmt}`;
  const a = document.createElement("a");
  a.href = url;
  // Append auth token as header won't work for direct download links — use a signed URL workaround via fetch+blob
  fetch(url, { headers: headers() })
    .then((r) => r.blob())
    .then((blob) => {
      const ext = fmt === "geojson" ? "geojson" : fmt;
      a.download = `track_${id.slice(0, 8)}.${ext}`;
      a.href = URL.createObjectURL(blob);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    })
    .catch(() => toasts.error("Export fehlgeschlagen"))
    .finally(() => { exportingId.value = null; });
}

async function finalizeActive() {
  const resp = await fetch(`${_BACKEND}/api/addons/${ADDON_ID}/finalize`, {
    method: "POST",
    headers: headers(),
  });
  if (resp.ok) {
    const body = await resp.json();
    active.value = { active: false };
    if (body.saved) {
      toasts.success("Track gespeichert");
      await fetchTracks();
    } else {
      toasts.error("Track zu kurz zum Speichern");
    }
  }
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

onMounted(async () => {
  await Promise.all([fetchTracks(), fetchActive()]);
  pollTimer = setInterval(fetchActive, 10_000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="tr-view">
    <!-- Not installed / 403 -->
    <div v-if="notInstalled" class="not-installed">
      <p>⚠ Track Recorder ist für deinen Account noch nicht aktiviert.</p>
      <p class="hint">Öffne den <strong>Marketplace</strong> und installiere das Add-on, oder starte GPS-Aufzeichnung — dann wird es automatisch aktiviert.</p>
    </div>

    <!-- Active recording banner -->
    <div v-if="active.active" class="active-banner">
      <div class="active-dot"></div>
      <div class="active-info">
        <span class="active-label">Aufnahme läuft</span>
        <span class="active-stats">
          {{ active.point_count }} Punkte · {{ active.distance_km?.toFixed(2) }} km
          <span v-if="active.start_time">· seit {{ fmtDate(active.start_time) }}</span>
        </span>
      </div>
      <button class="btn-finalize" @click="finalizeActive">Beenden</button>
    </div>

    <!-- Track list -->
    <p v-if="loading && !tracks.length" class="hint">Lade Tracks…</p>
    <p v-else-if="!tracks.length" class="empty-hint">
      Noch keine Tracks aufgezeichnet. Fahre los — Tracks werden automatisch gestartet.
    </p>

    <div v-for="track in tracks" :key="track.id" class="track-card">
      <div class="track-meta">
        <div class="track-header">
          <span class="track-date">{{ fmtDate(track.start_time) }}</span>
          <span v-if="track.locked" class="lock-badge" title="Gesperrt">🔒</span>
        </div>
        <div class="track-stats">
          <span>📍 {{ track.distance_km.toFixed(2) }} km</span>
          <span>⏱ {{ fmtDuration(track.start_time, track.end_time) }}</span>
          <span>⌀ {{ track.avg_speed.toFixed(0) }} km/h</span>
          <span>↑ {{ track.max_speed.toFixed(0) }} km/h</span>
        </div>
      </div>

      <div class="track-actions">
        <!-- Export dropdown -->
        <div class="export-group">
          <span class="export-label">Export:</span>
          <button
            v-for="fmt in ['gpx', 'geojson', 'kml', 'csv']"
            :key="fmt"
            class="btn-export"
            :disabled="exportingId === track.id"
            @click="exportTrack(track.id, fmt)"
          >{{ fmt.toUpperCase() }}</button>
        </div>

        <div class="icon-actions">
          <!-- Show on map -->
          <button
            class="btn-icon btn-map"
            :disabled="showingOnMapId === track.id"
            title="Auf Karte anzeigen"
            @click="showOnMap(track.id)"
          >🗺</button>

          <!-- Lock/Unlock -->
          <button
            class="btn-icon"
            :class="{ active: track.locked }"
            :disabled="lockingId === track.id"
            :title="track.locked ? 'Sperre aufheben' : 'Track sperren'"
            @click="toggleLock(track.id)"
          >{{ track.locked ? "🔓" : "🔒" }}</button>

          <!-- Delete -->
          <button
            class="btn-icon btn-delete"
            :disabled="deletingId === track.id || track.locked"
            :title="track.locked ? 'Entsperren um zu löschen' : 'Track löschen'"
            @click="deleteTrack(track.id)"
          >🗑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tr-view { display: flex; flex-direction: column; gap: 10px; }

.active-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #dcfce7;
  border: 1px solid #86efac;
  border-radius: 10px;
}
[data-theme="dark"] .active-banner { background: #14532d; border-color: #166534; }

.active-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #22c55e;
  flex-shrink: 0;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.active-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.active-label { font-size: 13px; font-weight: 700; color: #166534; }
[data-theme="dark"] .active-label { color: #86efac; }
.active-stats { font-size: 11px; color: #166534; opacity: 0.8; }
[data-theme="dark"] .active-stats { color: #86efac; }

.btn-finalize {
  padding: 5px 12px;
  background: #16a34a;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.track-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--bg-2);
  border: 1px solid var(--border-1);
  border-radius: 10px;
}

.track-meta { display: flex; flex-direction: column; gap: 4px; }

.track-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.track-date { font-size: 13px; font-weight: 600; color: var(--text-1); }
.lock-badge { font-size: 12px; }

.track-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text-3);
}

.track-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.export-group {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.export-label { font-size: 11px; color: var(--text-4); font-weight: 600; }

.btn-export {
  padding: 3px 8px;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-2);
  cursor: pointer;
}
.btn-export:hover { border-color: var(--accent); color: var(--accent); }
.btn-export:disabled { opacity: 0.4; cursor: not-allowed; }

.icon-actions { display: flex; gap: 6px; }

.btn-icon {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.btn-icon:hover { border-color: var(--accent); }
.btn-icon.active { border-color: #f59e0b; background: #fffbeb; }
[data-theme="dark"] .btn-icon.active { background: #451a03; border-color: #f59e0b; }
.btn-icon:disabled { opacity: 0.35; cursor: not-allowed; }

.btn-delete:hover:not(:disabled) { border-color: #ef4444; }
.btn-map:hover:not(:disabled) { border-color: #7c3aed; }

.not-installed {
  padding: 12px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 10px;
  font-size: 12px;
  color: #78350f;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
[data-theme="dark"] .not-installed { background: #1c1008; border-color: #92400e; color: #fcd34d; }
.not-installed p { margin: 0; }

.hint { margin: 0; font-size: 12px; color: var(--text-3); }
.empty-hint {
  margin: 0; font-size: 12px; color: var(--text-4);
  text-align: center; padding: 16px; line-height: 1.6;
}
</style>
