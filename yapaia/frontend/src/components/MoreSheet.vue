<script setup lang="ts">
import { computed } from "vue";
import { useMapStore } from "../stores/map";
import { usePreferencesStore } from "../stores/preferences";

const store = useMapStore();
const prefStore = usePreferencesStore();

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const ttsEnabled = computed(() => prefStore.data.tts_enabled !== false);
function toggleTts() { prefStore.set("tts_enabled", !ttsEnabled.value); }

function close() { emit("close"); }

// Selecting any action auto-closes the sheet — feels snappier than requiring
// a manual close gesture after a toggle.
function withClose(fn: () => void) {
  return () => { fn(); close(); };
}
</script>

<template>
  <Teleport to="body">
    <transition name="sheet">
      <div v-if="props.open" class="sheet-overlay" @click.self="close">
        <div class="sheet">
          <div class="sheet-handle"></div>
          <h3 class="sheet-title">Weitere Optionen</h3>

          <div class="sheet-grid">
            <button
              class="sheet-tile"
              :class="{ active: !ttsEnabled }"
              @click="withClose(toggleTts)()"
            >
              <span class="tile-icon">{{ ttsEnabled ? "🔊" : "🔇" }}</span>
              <span class="tile-label">{{ ttsEnabled ? "Sprachausgabe an" : "Sprachausgabe aus" }}</span>
            </button>

            <button
              class="sheet-tile"
              :class="{ active: store.mapPitch === 60 }"
              @click="withClose(() => store.toggle3D())()"
            >
              <span class="tile-icon">3D</span>
              <span class="tile-label">{{ store.mapPitch === 60 ? "3D-Ansicht an" : "3D-Ansicht aus" }}</span>
            </button>

            <button
              class="sheet-tile"
              :class="{ active: store.mapBearingMode === 'heading' }"
              @click="withClose(() => store.toggleBearingMode())()"
            >
              <span class="tile-icon compass-icon"
                    :style="{ transform: `rotate(${store.mapBearingMode === 'heading' ? -store.currentHeading : 0}deg)` }">
                🧭
              </span>
              <span class="tile-label">
                {{ store.mapBearingMode === "heading" ? "Fahrtrichtung oben" : "Norden oben" }}
              </span>
            </button>

            <button class="sheet-tile danger" @click="withClose(() => store.stopNavigation())()">
              <span class="tile-icon">⏹</span>
              <span class="tile-label">Navigation beenden</span>
            </button>
          </div>

          <button class="sheet-close" @click="close">Schließen</button>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 140;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.sheet {
  background: white;
  width: 100%;
  max-width: 520px;
  border-radius: 20px 20px 0 0;
  padding: 12px 16px 18px;
  box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.25);
}

.sheet-handle {
  width: 40px;
  height: 4px;
  background: #d1d5db;
  border-radius: 99px;
  margin: 0 auto 8px;
}

.sheet-title {
  margin: 0 0 14px;
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  text-align: center;
}

.sheet-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.sheet-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 8px;
  background: #f9fafb;
  border: 1.5px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 86px;
}

.sheet-tile:hover { background: #f3f4f6; }

.sheet-tile.active {
  background: #dbeafe;
  border-color: #3b82f6;
  color: #1e40af;
}

.sheet-tile.danger {
  background: #fee2e2;
  border-color: #fecaca;
  color: #991b1b;
}

.sheet-tile.danger:hover { background: #fecaca; }

.tile-icon {
  font-size: 24px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.tile-icon.compass-icon { transition: transform 0.3s; display: inline-block; }

.tile-label {
  font-size: 12px;
  font-weight: 600;
  text-align: center;
  line-height: 1.3;
}

.sheet-close {
  margin-top: 12px;
  width: 100%;
  padding: 10px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  cursor: pointer;
}

.sheet-close:hover { background: #f9fafb; }

.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .sheet, .sheet-leave-to .sheet { transform: translateY(20px); }
.sheet-enter-to .sheet, .sheet-leave-from .sheet { transform: translateY(0); }
.sheet-enter-active, .sheet-leave-active { transition: opacity 0.2s; }
.sheet-enter-active .sheet, .sheet-leave-active .sheet { transition: transform 0.25s ease-out; }
</style>
