<script setup lang="ts">
import { ref, computed } from "vue";
import { useMapStore } from "../stores/map";
import { useDraggable } from "../composables/useDraggable";

const store = useMapStore();
const open = ref(false);
const copied = ref(false);

const backendUrl = import.meta.env.VITE_BACKEND_URL || window.location.origin;
const pushUrl = computed(() => `${backendUrl}/api/gps/push?lat={lat}&lon={lon}&speed={speed}&heading={heading}`);

const sources = [
  { key: "browser"  as const, label: "Gerät (Browser)",     icon: "📱", desc: "GPS des anzeigenden Geräts" },
  { key: "server"   as const, label: "USB-Dongle (Server)", icon: "🔌", desc: "Serieller GPS-Empfänger am Server" },
  { key: "url"      as const, label: "URL (Extern)",        icon: "🔗", desc: "Externe GPS-App oder Tracker" },
  { key: "simulate" as const, label: "Simulator",           icon: "🎮", desc: "Fährt automatisch entlang der Route" },
];

function select(key: typeof sources[number]["key"]) {
  store.gpsSource = key;
  open.value = false;
  copied.value = false;
}

async function copyUrl() {
  await navigator.clipboard.writeText(pushUrl.value);
  copied.value = true;
  setTimeout(() => { copied.value = false; }, 2000);
}

function toggle() {
  open.value = !open.value;
  copied.value = false;
}

const activeSource = computed(
  () => sources.find((s) => s.key === store.gpsSource) ?? sources[0]
);

const d = useDraggable("gps-selector");
</script>

<template>
  <div
    class="gps-selector"
    :style="d.style.value"
    :class="{ dragging: d.active.value }"
    @pointerdown="d.onPointerDown"
    @pointermove="d.onPointerMove"
    @pointerup="d.onPointerUp"
    @pointercancel="d.onPointerCancel"
    @click.capture="d.guardClick"
  >
    <button class="gps-btn" :class="{ active: open }" @click="toggle"
            :title="'GPS-Quelle: ' + activeSource.label">
      {{ activeSource.icon }}
      <span class="gps-label">GPS</span>
    </button>

    <div v-if="open" class="gps-panel">
      <p class="panel-title">GPS-Quelle</p>

      <button
        v-for="s in sources"
        :key="s.key"
        class="source-btn"
        :class="{ selected: store.gpsSource === s.key, disabled: s.key === 'simulate' && !store.route }"
        :disabled="s.key === 'simulate' && !store.route"
        @click="select(s.key)"
      >
        <span class="s-icon">{{ s.icon }}</span>
        <span class="s-text">
          <strong>{{ s.label }}</strong>
          <small v-if="s.key === 'simulate' && !store.route">Erst Route berechnen</small>
          <small v-else>{{ s.desc }}</small>
        </span>
        <span v-if="store.gpsSource === s.key" class="s-check">✓</span>
      </button>

      <!-- URL Push Info -->
      <div v-if="store.gpsSource === 'url'" class="info-box">
        <p class="info-label">Push-URL für GPS-Logger:</p>
        <div class="push-row">
          <code class="push-code">{{ pushUrl }}</code>
          <button class="copy-btn" @click="copyUrl">{{ copied ? "✓" : "📋" }}</button>
        </div>
        <p class="info-hint">Platzhalter werden von GPS-Apps automatisch ersetzt.</p>
      </div>

      <!-- Server GPS Info -->
      <div v-if="store.gpsSource === 'server'" class="info-box">
        <p>USB-GPS-Dongle muss am Server eingesteckt und in <code class="inline">.env</code> konfiguriert sein:</p>
        <code class="block-code">GPS_SERIAL_PORT=/dev/ttyUSB0</code>
      </div>

      <!-- Simulator Info -->
      <div v-if="store.gpsSource === 'simulate'" class="info-box sim-info">
        <p>Simulator fährt die berechnete Route ab.</p>
        <p>Navigation starten, um die Abbiege&shy;anweisungen zu testen.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gps-selector {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 20;
  touch-action: none;
}

.gps-selector.dragging {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 12px;
  cursor: grabbing;
  opacity: 0.9;
  z-index: 30;
}

.gps-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: var(--bg);
  border: none;
  border-radius: 10px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  font-size: 16px;
  transition: background 0.15s;
}

.gps-btn:hover, .gps-btn.active {
  background: var(--accent-bg);
}

.gps-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
}

.gps-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 290px;
  background: var(--bg);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.panel-title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.source-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1.5px solid var(--border-1);
  border-radius: 10px;
  background: var(--bg);
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: border-color 0.15s, background 0.15s;
}

.source-btn:hover:not(:disabled) {
  background: var(--bg-2);
}

.source-btn.selected {
  border-color: var(--accent);
  background: var(--accent-bg);
}

.source-btn.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.s-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.s-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.s-text strong {
  font-size: 13px;
  color: var(--text-1);
}

.s-text small {
  font-size: 11px;
  color: var(--text-4);
}

.s-check {
  color: var(--accent);
  font-weight: 700;
}

.info-box {
  padding: 10px;
  background: var(--bg-2);
  border-radius: 8px;
  border: 1px solid var(--border-1);
  font-size: 11px;
  color: var(--text-2);
  line-height: 1.5;
}

.info-box p {
  margin: 0 0 6px;
}

.info-box p:last-child {
  margin-bottom: 0;
}

.info-label {
  font-weight: 600;
  color: var(--text-2);
}

.push-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.push-code {
  flex: 1;
  font-size: 10px;
  color: var(--text-2);
  background: var(--bg-input);
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-2);
  word-break: break-all;
  line-height: 1.4;
}

.copy-btn {
  padding: 4px 8px;
  border: none;
  background: var(--accent);
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  flex-shrink: 0;
}

.info-hint {
  font-size: 10px;
  color: var(--text-4);
  margin: 0 !important;
}

.inline {
  background: var(--bg-input);
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid var(--border-2);
  font-size: 11px;
}

.block-code {
  display: block;
  background: var(--bg-input);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-2);
  font-size: 11px;
  color: var(--accent-text);
}

.sim-info {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}
</style>
