<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import { useMapStore } from "../stores/map";
import { useUiStore } from "../stores/ui";

const store = useMapStore();
const uiStore = useUiStore();

// Ticking clock so ETA reflects the real wall time, not the moment of the
// last reactive recompute. Without this, ETA can lag minutes behind reality.
const nowMs = ref(Date.now());
let tickHandle: number | null = null;
onMounted(() => {
  tickHandle = window.setInterval(() => { nowMs.value = Date.now(); }, 1000);
});
onBeforeUnmount(() => {
  if (tickHandle !== null) window.clearInterval(tickHandle);
});

const SIGN_ARROW: Record<number, string> = {
  [-98]: "⤺", [-8]: "⤺",
  [-7]: "↖", [-3]: "⬅", [-2]: "←", [-1]: "↖",
  0: "↑",
  1: "↗", 2: "→", 3: "➡",
  4: "🏁", 5: "📍",
  6: "⟳", 7: "↗", 8: "⤺",
};

function arrow(sign: number): string {
  return SIGN_ARROW[sign] ?? "↑";
}

function fmtDist(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function fmtTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

function fmtEta(seconds: number, baseMs: number): string {
  const arrival = new Date(baseMs + seconds * 1000);
  return arrival.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

const summary = computed(() => {
  if (!store.route) return null;
  const dist = store.isNavigating ? store.remainingDistance : store.route.distance;
  const time = store.isNavigating ? store.remainingDuration : store.route.duration;
  return {
    dist: fmtDist(dist),
    time: fmtTime(time),
    eta: fmtEta(time, nowMs.value),
  };
});

const showPanel = computed(() => {
  if (!store.route) return false;
  // Always show when route exists and either: not navigating, or panel manually expanded
  return !store.isNavigating || store.isPanelExpanded;
});
</script>

<template>
  <!-- Compact bottom bar (during navigation, panel collapsed) -->
  <div v-if="store.route && store.isNavigating && !store.isPanelExpanded" class="bottom-bar">
    <div class="bb-item">
      <span class="bb-label">Ankunft</span>
      <span class="bb-value">{{ summary?.eta }}</span>
    </div>
    <div class="bb-divider"></div>
    <div class="bb-item">
      <span class="bb-label">Restzeit</span>
      <span class="bb-value">{{ summary?.time }}</span>
    </div>
    <div class="bb-divider"></div>
    <div class="bb-item">
      <span class="bb-label">Distanz</span>
      <span class="bb-value">{{ summary?.dist }}</span>
    </div>
    <button class="bb-btn" @click="uiStore.settingsOpen = true" title="Einstellungen">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    </button>
    <button class="bb-btn expand" @click="store.togglePanel()" title="Liste anzeigen">▲</button>
    <button class="bb-btn stop" @click="store.stopNavigation()" title="Navigation beenden">✕</button>
  </div>

  <!-- Full panel (route preview before nav, or expanded during nav) -->
  <div v-if="showPanel" class="route-panel" :class="{ navigating: store.isNavigating }">
    <div class="summary-bar">
      <span class="summary-dist">{{ summary?.dist }}</span>
      <span class="summary-time">
        {{ summary?.time }}
        <small v-if="store.isNavigating">· {{ summary?.eta }}</small>
      </span>
      <button
        v-if="!store.isNavigating"
        class="nav-btn"
        :class="{ preview: !store.canStartNavigation }"
        :disabled="!store.canStartNavigation"
        :title="store.canStartNavigation ? '' : 'Navigation nur startbar wenn Sie nahe am Startpunkt sind. Andernfalls Routenvorschau — oder GPS-Simulator aktivieren.'"
        @click="store.startNavigation()"
      >{{ store.canStartNavigation ? "▶ Navigation" : "👁 Vorschau" }}</button>
      <button
        v-else
        class="nav-btn stop"
        @click="store.stopNavigation()"
      >⏹ Stop</button>
      <button v-if="store.isNavigating" class="collapse-btn" @click="store.togglePanel()" title="Einklappen">▼</button>
      <button v-else class="close-btn" @click="store.clearRoute()">✕</button>
    </div>

    <ul class="instructions">
      <li
        v-for="(inst, idx) in store.route?.instructions"
        :key="idx"
        :class="{ active: idx === store.currentStep && store.isNavigating, past: idx < store.currentStep && store.isNavigating }"
      >
        <span class="arrow">{{ arrow(inst.sign) }}</span>
        <span class="inst-text">{{ inst.text }}<small v-if="inst.street"> · {{ inst.street }}</small></span>
        <span class="inst-dist">{{ fmtDist(inst.distance) }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.route-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
  max-height: 50vh;
  display: flex;
  flex-direction: column;
  z-index: 10;
}

.summary-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-3);
  flex-shrink: 0;
}

.summary-dist {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-1);
}

.summary-time {
  font-size: 15px;
  color: var(--text-3);
  flex: 1;
}

.summary-time small {
  font-size: 13px;
  margin-left: 4px;
  color: var(--text-4);
}

.nav-btn {
  padding: 8px 16px;
  background: #22c55e;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.nav-btn.stop {
  background: #ef4444;
}

.nav-btn.preview {
  background: var(--text-4);
  cursor: not-allowed;
}

.close-btn, .collapse-btn {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: var(--text-4);
  padding: 4px 8px;
}

.collapse-btn:hover {
  color: var(--text-2);
}

.instructions {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
}

.instructions li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-3);
  font-size: 13px;
}

.instructions li.active {
  background: var(--accent-bg-2);
  font-weight: 600;
}

.instructions li.past {
  opacity: 0.4;
}

.arrow {
  font-size: 18px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}

.inst-text {
  flex: 1;
  color: var(--text-2);
}

.inst-text small {
  color: var(--text-4);
}

.inst-dist {
  color: var(--text-3);
  white-space: nowrap;
}

/* ───────── Compact bottom bar during navigation ───────── */
.bottom-bar {
  position: absolute;
  bottom: 12px;
  left: 12px;
  right: 12px;
  max-width: 560px;
  margin: 0 auto;
  background: var(--bg);
  border-radius: 14px;
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: center;
  padding: 10px 14px;
  gap: 10px;
  z-index: 12;
}

.bb-item {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.bb-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bb-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-1);
  white-space: nowrap;
}

.bb-divider {
  width: 1px;
  height: 28px;
  background: var(--border-1);
}

.bb-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  transition: background 0.15s;
}

.bb-btn.expand {
  background: var(--bg-3);
  color: var(--text-2);
}

.bb-btn.expand:hover {
  background: var(--border-1);
}

.bb-btn.stop {
  background: #ef4444;
  color: white;
}

.bb-btn.stop:hover {
  background: #dc2626;
}
</style>
