<script setup lang="ts">
import { computed } from "vue";
import { usePreferencesStore } from "../stores/preferences";
import { MAP_STYLES, DEFAULT_LIGHT, DEFAULT_DARK } from "../services/mapStyles";

const prefs = usePreferencesStore();

const styles = Object.values(MAP_STYLES);

const selectedLight = computed(() => prefs.data.map_style_light ?? DEFAULT_LIGHT);
const selectedDark  = computed(() => prefs.data.map_style_dark  ?? DEFAULT_DARK);
</script>

<template>
  <div class="ms-view">
    <!-- ── Hell-Modus ───────────────────────────────────────────────── -->
    <div class="ms-section-title">☀️ Hell-Modus</div>
    <div class="ms-grid">
      <button
        v-for="s in styles"
        :key="'l-' + s.id"
        class="ms-card"
        :class="{ selected: selectedLight === s.id }"
        @click="prefs.set('map_style_light', s.id)"
      >
        <div class="ms-swatch" :style="{ background: s.previewColor }">
          <span v-if="selectedLight === s.id" class="ms-check">✓</span>
        </div>
        <div class="ms-label">
          <span class="ms-name">{{ s.name }}</span>
          <span class="ms-desc">{{ s.description }}</span>
        </div>
      </button>
    </div>

    <!-- ── Dunkel-Modus ─────────────────────────────────────────────── -->
    <div class="ms-section-title" style="margin-top: 16px;">🌙 Dunkel-Modus</div>
    <div class="ms-grid">
      <button
        v-for="s in styles"
        :key="'d-' + s.id"
        class="ms-card"
        :class="{ selected: selectedDark === s.id }"
        @click="prefs.set('map_style_dark', s.id)"
      >
        <div class="ms-swatch" :style="{ background: s.previewColor }">
          <span v-if="selectedDark === s.id" class="ms-check">✓</span>
        </div>
        <div class="ms-label">
          <span class="ms-name">{{ s.name }}</span>
          <span class="ms-desc">{{ s.description }}</span>
        </div>
      </button>
    </div>

    <p class="ms-hint">Änderungen werden sofort auf die Karte angewendet.</p>
  </div>
</template>

<style scoped>
.ms-view { display: flex; flex-direction: column; gap: 8px; }

.ms-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-2);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-1);
}

.ms-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.ms-card {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--bg-2);
  border: 2px solid var(--border-1);
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  padding: 0;
  transition: border-color 0.15s;
}
.ms-card:hover { border-color: var(--accent); }
.ms-card.selected { border-color: var(--accent); background: var(--accent-bg); }

.ms-swatch {
  width: 100%;
  height: 52px;
  position: relative;
  flex-shrink: 0;
}

.ms-check {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 900;
  color: white;
  text-shadow: 0 1px 4px rgba(0,0,0,0.6);
}

.ms-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
}

.ms-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1.2;
}

.ms-desc {
  font-size: 10px;
  color: var(--text-4);
  line-height: 1.3;
}

.ms-hint {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-4);
  text-align: center;
}
</style>
