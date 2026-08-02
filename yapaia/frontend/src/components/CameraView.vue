<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, computed } from "vue";
import { useDraggable } from "../composables/useDraggable";
import { useCameraStore, QUALITY_OPTIONS } from "../stores/camera";

const backendUrl = import.meta.env.VITE_BACKEND_URL || "";
const streamBaseUrl = window.location.origin;

const videoEl = ref<HTMLVideoElement | null>(null);
const open = ref(false);
const errorMsg = ref("");
const settingsOpen = ref(false);
function copyStreamUrl(url: string) { navigator.clipboard.writeText(url).catch(() => {}); }

const cameraStore = useCameraStore();
const dBtn = useDraggable("cam-btn");
const dWin = useDraggable("cam-win");

// ── Display camera ──────────────────────────────────────────────────────────
let displayStream: MediaStream | null = null;
const displayIdx = ref(0);

async function startDisplay(deviceId?: string) {
  displayStream?.getTracks().forEach((t) => t.stop());
  displayStream = null;
  if (videoEl.value) videoEl.value.srcObject = null;
  errorMsg.value = "";
  try {
    displayStream = await navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId } } : { facingMode: "environment" },
    });
    if (videoEl.value) videoEl.value.srcObject = displayStream;

    // Re-enumerate after permission grant so labels appear
    const all = await navigator.mediaDevices.enumerateDevices();
    cameraStore.devices = all.filter((d) => d.kind === "videoinput");
    const activeId = displayStream.getVideoTracks()[0]?.getSettings().deviceId;
    const idx = cameraStore.devices.findIndex((c) => c.deviceId === activeId);
    if (idx >= 0) displayIdx.value = idx;

    // Sync background streams whenever we (re-)enumerate
    syncStreams();
  } catch {
    errorMsg.value = "Kamera konnte nicht gestartet werden";
  }
}

function stopDisplay() {
  displayStream?.getTracks().forEach((t) => t.stop());
  displayStream = null;
  if (videoEl.value) videoEl.value.srcObject = null;
}

async function toggle() {
  if (open.value) {
    open.value = false;
    stopDisplay();
  } else {
    open.value = true;
    await nextTick();
    await startDisplay();
  }
}

async function nextCamera() {
  if (cameraStore.devices.length <= 1) return;
  displayIdx.value = (displayIdx.value + 1) % cameraStore.devices.length;
  await startDisplay(cameraStore.devices[displayIdx.value].deviceId);
}

function close() {
  open.value = false;
  stopDisplay();
}

// ── Background MJPEG streams ────────────────────────────────────────────────
interface ActiveStream {
  stream: MediaStream;
  video: HTMLVideoElement;
  canvas: HTMLCanvasElement;
  ws: WebSocket;
  intervalId: ReturnType<typeof setInterval>;
}

const activeStreams = new Map<number, ActiveStream>();
const streamCount = ref(0); // reactive counter for template

async function startStream(idx: number) {
  const cam = cameraStore.devices[idx];
  if (!cam) return;
  stopStream(idx); // clean up any previous

  try {
    const ms = await navigator.mediaDevices.getUserMedia({
      video: { deviceId: { exact: cam.deviceId } },
    });
    const vid = document.createElement("video");
    vid.muted = true;
    vid.playsInline = true;
    vid.autoplay = true;
    vid.srcObject = ms;
    await vid.play();

    const q = QUALITY_OPTIONS.find((o) => o.key === cameraStore.getConfig(idx).quality)
      ?? QUALITY_OPTIONS[1];

    const wsBase = backendUrl.replace(/^http/, "ws") || `${location.protocol.replace("http", "ws")}//${location.host}`;
    const ws = new WebSocket(`${wsBase}/ws/camera/${idx}`);

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d")!;

    const intervalId = setInterval(() => {
      if (!vid.videoWidth || ws.readyState !== WebSocket.OPEN) return;
      const scale = Math.min(1, q.width / vid.videoWidth);
      canvas.width = Math.round(vid.videoWidth * scale);
      canvas.height = Math.round(vid.videoHeight * scale);
      ctx.drawImage(vid, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => { blob?.arrayBuffer().then((buf) => { if (ws.readyState === WebSocket.OPEN) ws.send(buf); }); },
        "image/jpeg",
        q.jpegQuality,
      );
    }, 1000 / q.fps);

    activeStreams.set(idx, { stream: ms, video: vid, canvas, ws, intervalId });
    streamCount.value = activeStreams.size;
  } catch (e) {
    console.warn(`Camera stream ${idx} failed:`, e);
  }
}

function stopStream(idx: number) {
  const s = activeStreams.get(idx);
  if (!s) return;
  clearInterval(s.intervalId);
  s.ws.close();
  s.stream.getTracks().forEach((t) => t.stop());
  activeStreams.delete(idx);
  streamCount.value = activeStreams.size;
}

function stopAllStreams() {
  for (const idx of activeStreams.keys()) stopStream(idx);
}

async function syncStreams() {
  for (let i = 0; i < cameraStore.devices.length; i++) {
    const cfg = cameraStore.getConfig(i);
    if (cfg.enabled && !activeStreams.has(i)) {
      await startStream(i);
    } else if (!cfg.enabled && activeStreams.has(i)) {
      stopStream(i);
    } else if (cfg.enabled && activeStreams.has(i)) {
      // Quality changed → restart
      await startStream(i);
    }
  }
  // Remove streams for cameras that no longer exist
  for (const idx of activeStreams.keys()) {
    if (idx >= cameraStore.devices.length) stopStream(idx);
  }
}

// React to config changes from SettingsModal
watch(() => cameraStore.configs, () => {
  if (cameraStore.devices.length > 0) syncStreams();
}, { deep: true });

onBeforeUnmount(() => {
  stopDisplay();
  stopAllStreams();
});
</script>

<template>
  <!-- Toggle button -->
  <button
    class="cam-btn"
    :class="{ active: open, dragging: dBtn.active.value }"
    :style="dBtn.style.value"
    title="Kamera"
    @pointerdown="dBtn.onPointerDown"
    @pointermove="dBtn.onPointerMove"
    @pointerup="dBtn.onPointerUp"
    @pointercancel="dBtn.onPointerCancel"
    @click.capture="dBtn.guardClick"
    @click="toggle"
  >
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M23 7l-7 5 7 5V7z"/>
      <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
    </svg>
  </button>

  <!-- Camera display window -->
  <Teleport to="body">
    <div
      v-if="open"
      class="cam-win"
      :class="{ dragging: dWin.active.value }"
      :style="dWin.style.value"
      @pointerdown="dWin.onPointerDown"
      @pointermove="dWin.onPointerMove"
      @pointerup="dWin.onPointerUp"
      @pointercancel="dWin.onPointerCancel"
      @click.capture="dWin.guardClick"
    >
      <div class="cam-toolbar">
        <svg class="cam-grip" viewBox="0 0 20 10" width="16" height="8" fill="currentColor" aria-hidden="true">
          <rect y="0" width="20" height="2" rx="1"/>
          <rect y="4" width="20" height="2" rx="1"/>
          <rect y="8" width="20" height="2" rx="1"/>
        </svg>
        <span class="cam-label">
          {{ cameraStore.devices.length > 1
              ? `Kamera ${displayIdx + 1} / ${cameraStore.devices.length}`
              : "Kamera" }}
        </span>
        <!-- Streaming indicator -->
        <span
          v-if="streamCount > 0"
          class="stream-badge"
          :title="`${streamCount} Stream(s) aktiv`"
        >● LIVE</span>
        <button
          v-if="cameraStore.devices.length > 1"
          class="cam-ctrl"
          title="Kamera wechseln"
          @click="nextCamera"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="1 4 1 10 7 10"/>
            <polyline points="23 20 23 14 17 14"/>
            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
          </svg>
        </button>
        <button class="cam-ctrl" title="Stream-Einstellungen" @click="settingsOpen = !settingsOpen">⚙</button>
        <button class="cam-ctrl cam-close" title="Schließen" @click="close">✕</button>
      </div>
      <div class="cam-body">
        <video v-if="!errorMsg" ref="videoEl" autoplay muted playsinline class="cam-video" />
        <div v-else class="cam-error">{{ errorMsg }}</div>
      </div>

      <!-- Stream settings panel -->
      <div v-if="settingsOpen" class="cam-settings">
        <div v-if="cameraStore.devices.length === 0" class="cam-settings-hint">
          Kamera öffnen, um Streams zu konfigurieren.
        </div>
        <div v-else v-for="(cam, idx) in cameraStore.devices" :key="cam.deviceId" class="cam-stream-row">
          <div class="cam-stream-header">
            <span class="cam-stream-name">{{ cam.label || `Kamera ${idx + 1}` }}</span>
            <label class="cam-toggle">
              <input
                type="checkbox"
                :checked="cameraStore.getConfig(idx).enabled"
                @change="cameraStore.setConfig(idx, { enabled: ($event.target as HTMLInputElement).checked })"
              />
              <span class="cam-toggle-slider"></span>
            </label>
          </div>
          <template v-if="cameraStore.getConfig(idx).enabled">
            <div class="cam-quality-chips">
              <button
                v-for="q in QUALITY_OPTIONS"
                :key="q.key"
                class="cam-q-chip"
                :class="{ active: cameraStore.getConfig(idx).quality === q.key }"
                @click="cameraStore.setConfig(idx, { quality: q.key })"
              >{{ q.label }}</button>
            </div>
            <div class="cam-url-row">
              <code class="cam-url-text">{{ streamBaseUrl }}/api/camera/stream/{{ idx }}</code>
              <button class="cam-copy-btn" title="URL kopieren" @click="copyStreamUrl(`${streamBaseUrl}/api/camera/stream/${idx}`)">📋</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Toggle button ────────────────────────────────────────────────────── */
.cam-btn {
  position: absolute;
  bottom: 100px;
  left: 12px;
  z-index: 16;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: var(--bg);
  color: var(--text-1);
  cursor: pointer;
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: center;
  justify-content: center;
  touch-action: none;
  transition: background 0.15s, color 0.15s;
}
.cam-btn:hover { background: var(--bg-3); }
.cam-btn.active { background: var(--accent); color: white; }
.cam-btn.dragging {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  cursor: grabbing;
  opacity: 0.9;
  z-index: 30;
}

/* ── Camera window ────────────────────────────────────────────────────── */
.cam-win {
  position: fixed;
  bottom: 160px;
  left: 12px;
  z-index: 50;
  width: 220px;
  border-radius: 12px;
  overflow: hidden;
  background: #111;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55);
  touch-action: none;
}
.cam-win.dragging {
  outline: 2px solid var(--accent);
  cursor: grabbing;
  z-index: 60;
}

.cam-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  background: rgba(0, 0, 0, 0.8);
  user-select: none;
}

.cam-grip { color: rgba(255, 255, 255, 0.3); flex-shrink: 0; }

.cam-label {
  flex: 1;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.75);
  font-weight: 600;
}

.stream-badge {
  font-size: 9px;
  font-weight: 700;
  color: #4ade80;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.cam-ctrl {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.65);
  font-size: 13px;
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: background 0.12s, color 0.12s;
}
.cam-ctrl:hover { background: rgba(255, 255, 255, 0.15); color: white; }
.cam-close { font-size: 12px; }

/* ── Video / Error ────────────────────────────────────────────────────── */
.cam-body { position: relative; }

.cam-video {
  display: block;
  width: 100%;
  height: auto;
  max-height: 170px;
  object-fit: cover;
  background: #000;
}

.cam-error {
  height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #f87171;
  padding: 16px;
  text-align: center;
  line-height: 1.5;
}

/* ── Stream settings panel ─────────────────────────────────────────── */
.cam-settings {
  padding: 10px;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cam-settings-hint { font-size: 11px; color: rgba(255,255,255,0.5); text-align: center; }

.cam-stream-row { display: flex; flex-direction: column; gap: 6px; }

.cam-stream-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cam-stream-name { font-size: 11px; color: rgba(255,255,255,0.75); font-weight: 600; }

.cam-toggle { position: relative; width: 34px; height: 18px; flex-shrink: 0; }
.cam-toggle input { opacity: 0; width: 0; height: 0; }
.cam-toggle-slider {
  position: absolute; inset: 0; border-radius: 9px;
  background: rgba(255,255,255,0.2); cursor: pointer; transition: background 0.2s;
}
.cam-toggle input:checked + .cam-toggle-slider { background: #3b82f6; }
.cam-toggle-slider::before {
  content: ""; position: absolute; width: 12px; height: 12px;
  border-radius: 50%; background: white; left: 3px; top: 3px; transition: transform 0.2s;
}
.cam-toggle input:checked + .cam-toggle-slider::before { transform: translateX(16px); }

.cam-quality-chips { display: flex; gap: 4px; flex-wrap: wrap; }
.cam-q-chip {
  padding: 3px 7px; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px;
  background: transparent; color: rgba(255,255,255,0.6); font-size: 10px; cursor: pointer;
}
.cam-q-chip.active { background: #3b82f6; border-color: #3b82f6; color: white; }

.cam-url-row { display: flex; align-items: center; gap: 4px; }
.cam-url-text { font-size: 9px; color: rgba(255,255,255,0.5); word-break: break-all; flex: 1; }
.cam-copy-btn {
  background: none; border: none; cursor: pointer; font-size: 12px;
  padding: 2px 4px; border-radius: 4px; flex-shrink: 0;
}
.cam-copy-btn:hover { background: rgba(255,255,255,0.1); }
</style>
