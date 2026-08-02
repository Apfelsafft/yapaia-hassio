<script setup lang="ts">
import { computed } from "vue";
import { useMapStore } from "../stores/map";
import { usePreferencesStore } from "../stores/preferences";
import { useDraggable } from "../composables/useDraggable";

const store = useMapStore();
const prefStore = usePreferencesStore();
const ttsEnabled = computed(() => prefStore.data.tts_enabled !== false);
function toggleTts() { prefStore.set("tts_enabled", !ttsEnabled.value); }

const overSpeed = computed(
  () =>
    store.currentSpeedLimit != null &&
    store.currentSpeed > store.currentSpeedLimit + 5,
);

const isUserCentered = computed(() => {
  const pos = store.userPosition;
  const center = store.mapCenter;
  if (!pos) return true;
  const dLat = (pos[1] - center[1]) * 111_320;
  const dLon = (pos[0] - center[0]) * 111_320 * Math.cos((pos[1] * Math.PI) / 180);
  return Math.sqrt(dLat * dLat + dLon * dLon) < 50;
});

const d = useDraggable("nav-controls");

function zoomToLocation() {
  if (store.userPosition) {
    store.zoomToUserLocation();
    return;
  }
  if (!("geolocation" in navigator)) return;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      store.userPosition = [pos.coords.longitude, pos.coords.latitude];
      store.zoomToUserLocation();
    },
    () => {},
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
  );
}
</script>

<template>
  <div
    class="nav-controls"
    :style="d.style.value"
    :class="{ dragging: d.active.value }"
    @pointerdown="d.onPointerDown"
    @pointermove="d.onPointerMove"
    @pointerup="d.onPointerUp"
    @pointercancel="d.onPointerCancel"
    @click.capture="d.guardClick"
  >
    <button
      class="ctrl-btn"
      @click="zoomToLocation()"
      title="Auf aktuellen Standort zoomen"
    >
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
        <circle cx="12" cy="12" r="6"/>
        <line x1="12" y1="2" x2="12" y2="6"/>
        <line x1="12" y1="18" x2="12" y2="22"/>
        <line x1="2" y1="12" x2="6" y2="12"/>
        <line x1="18" y1="12" x2="22" y2="12"/>
      </svg>
    </button>

    <!-- Navigation-only controls -->
    <template v-if="store.isNavigating">
      <button
        class="ctrl-btn"
        :class="{ active: store.mapPitch === 60 }"
        @click="store.toggle3D()"
        title="3D-Ansicht"
      >
        <span class="ctrl-icon">3D</span>
      </button>

      <button
        class="ctrl-btn"
        :class="{ active: store.mapBearingMode === 'heading' }"
        @click="store.toggleBearingMode()"
        :title="store.mapBearingMode === 'heading' ? 'Norden oben' : 'Fahrtrichtung oben'"
      >
        <span class="compass" :style="{ transform: `rotate(${store.mapBearingMode === 'heading' ? -store.currentHeading : 0}deg)` }">
          🧭
        </span>
      </button>

      <button
        v-if="!store.followUser"
        class="ctrl-btn recenter"
        @click="store.followUser = true"
        title="Auf aktuellen Standort zentrieren"
      >
        <span class="ctrl-icon">📍</span>
      </button>

      <button
        class="ctrl-btn"
        :class="{ active: !ttsEnabled }"
        @click="toggleTts"
        :title="ttsEnabled ? 'Sprachausgabe ausschalten' : 'Sprachausgabe einschalten'"
      >
        <span class="ctrl-icon">{{ ttsEnabled ? "🔊" : "🔇" }}</span>
      </button>

      <div class="speed-chip" :class="{ warn: overSpeed }">
        <span class="speed-val">{{ Math.round(store.currentSpeed) }}</span>
        <span class="speed-unit">km/h</span>
      </div>

      <div v-if="store.currentSpeedLimit != null" class="limit-sign" :title="`Tempolimit ${store.currentSpeedLimit} km/h`">
        {{ Math.round(store.currentSpeedLimit) }}
      </div>

      <!-- Time-lapse control — nur beim GPS-Simulator -->
      <div v-if="store.gpsSource === 'simulate'" class="sim-speed">
        <button class="sim-btn" @click="store.stepSimulatorMultiplier(-1)" :disabled="store.simulatorMultiplier <= 0.5">−</button>
        <span class="sim-val">{{ store.simulatorMultiplier }}×</span>
        <button class="sim-btn" @click="store.stepSimulatorMultiplier(1)" :disabled="store.simulatorMultiplier >= 10">+</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.nav-controls {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 14;
  touch-action: none;
}

.nav-controls.dragging {
  outline: 2px solid var(--accent);
  outline-offset: 4px;
  border-radius: 18px;
  cursor: grabbing;
  opacity: 0.9;
  z-index: 30;
}

.ctrl-btn {
  width: 52px;
  height: 52px;
  border: none;
  border-radius: 14px;
  background: var(--bg);
  color: var(--text-1);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.ctrl-btn:hover {
  background: var(--bg-3);
}

.ctrl-btn.active {
  background: var(--accent);
  color: white;
}

.ctrl-btn.recenter {
  background: var(--accent);
  color: white;
}

.ctrl-btn.recenter:hover {
  background: var(--accent-dark);
}

.ctrl-icon {
  font-size: 15px;
  letter-spacing: -0.5px;
}

.compass {
  display: inline-block;
  font-size: 22px;
  transition: transform 0.3s;
}

.speed-chip {
  background: var(--bg);
  border-radius: 14px;
  padding: 8px 12px;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 52px;
}

.speed-val {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-1);
  line-height: 1;
}

.speed-unit {
  font-size: 10px;
  color: var(--text-3);
  margin-top: 2px;
}

.speed-chip.warn {
  background: #fee2e2;
  outline: 2px solid #ef4444;
}

.speed-chip.warn .speed-val {
  color: #b91c1c;
}

.sim-speed {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: var(--bg);
  border-radius: 14px;
  padding: 6px 8px;
  box-shadow: var(--shadow-sm);
}

.sim-btn {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 8px;
  background: var(--bg-3);
  color: var(--text-1);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.sim-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.sim-btn:not(:disabled):hover { background: var(--accent); color: white; }

.sim-val {
  font-size: 13px;
  font-weight: 800;
  color: var(--accent);
  min-width: 28px;
  text-align: center;
}

/* German-style round red-border speed limit sign */
.limit-sign {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--bg);
  border: 5px solid #dc2626;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-1);
  box-shadow: var(--shadow-sm);
}
</style>
