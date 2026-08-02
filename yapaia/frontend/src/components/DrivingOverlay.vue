<script setup lang="ts">
import { computed } from "vue";
import { useMapStore } from "../stores/map";
import TurnIcon from "./TurnIcon.vue";

const store = useMapStore();

function fmtDist(m: number): string {
  if (m >= 1000) return `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km`;
  if (m >= 100) return `${Math.round(m / 10) * 10} m`;
  return `${Math.round(m)} m`;
}

const inst = computed(() => store.nextTurnInstruction);
const liveDistance = computed(() => store.distanceToNextTurn);
const afterInst = computed(() => store.afterNextTurnInstruction);
</script>

<template>
  <div v-if="store.isNavigating && inst" class="driving-overlay">
    <!-- Primary row: next turn -->
    <div class="main-row">
      <div class="arrow-col">
        <TurnIcon :sign="inst.sign" :exit-number="inst.exit_number" :size="84"/>
      </div>
      <div class="info-col">
        <p class="distance">{{ fmtDist(liveDistance) }}</p>
        <p class="street">{{ inst.street || inst.text }}</p>
        <p class="sub-text" v-if="inst.street && inst.text !== inst.street">{{ inst.text }}</p>
      </div>
      <button class="exit-btn" @click="store.stopNavigation()" title="Navigation beenden">✕</button>
    </div>

    <!-- Secondary strip: turn after next -->
    <div v-if="afterInst" class="after-next">
      <span class="after-label">danach</span>
      <TurnIcon :sign="afterInst.sign" :exit-number="afterInst.exit_number" :size="26"/>
      <span class="after-street">{{ afterInst.street || afterInst.text }}</span>
    </div>
  </div>
</template>

<style scoped>
.driving-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: #1e3a8a;
  color: white;
  display: flex;
  flex-direction: column;
  z-index: 15;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
}

.main-row {
  display: flex;
  align-items: stretch;
  min-height: 120px;
}

.arrow-col {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 130px;
  flex-shrink: 0;
  background: #1d4ed8;
}

.info-col {
  flex: 1;
  padding: 14px 18px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.distance {
  margin: 0;
  font-size: 54px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -1px;
}

.street {
  margin: 6px 0 0;
  font-size: 22px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.95;
}

.sub-text {
  margin: 4px 0 0;
  font-size: 14px;
  opacity: 0.7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.exit-btn {
  align-self: flex-start;
  margin: 10px 10px 0 0;
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  color: white;
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}

.exit-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* ── After-next strip ──────────────────────────────────────────────────── */
.after-next {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 14px 5px 12px;
  background: #1e40af;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.after-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.55);
  flex-shrink: 0;
}

.after-street {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
