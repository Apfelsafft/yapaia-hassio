<script setup lang="ts">
import { ref, computed } from "vue";
import { useUserStore } from "../stores/user";
import { useAddonsStore } from "../stores/addons";
import { useVoiceInput } from "../composables/useVoiceInput";
import type { SearchResult } from "../stores/map";
import { searchUrl } from "../services/serviceUrl";

const emit = defineEmits<{
  apply: [payload: {
    destination: SearchResult;
    waypoints: SearchResult[];
    profile: string;
    avoid: string[];
    routing_strategy: string;
    notes: string;
  }];
  close: [];
}>();

const userStore = useUserStore();
const addonsStore = useAddonsStore();
const backendUrl = import.meta.env.VITE_BACKEND_URL || "";

const { start: startVoice, isListening, isSupported: voiceSupported } = useVoiceInput();

const text = ref("");
const parsing = ref(false);
const error = ref("");
const parsed = ref<{
  destination: string;
  profile: string;
  waypoints: string[];
  avoid: string[];
  prefer_scenic: boolean;
  routing_strategy: string;
  notes: string;
} | null>(null);
const geocoding = ref(false);
const geocoded = ref<{
  destination: SearchResult | null;
  waypoints: (SearchResult | null)[];
} | null>(null);

const profileLabel: Record<string, string> = {
  car: "🚗 PKW",
  bike: "🚲 Fahrrad",
  foot: "🚶 Fuß",
  motorhome: "🚐 Wohnmobil",
};

const strategyLabel: Record<string, string> = {
  fastest: "Schnellste Route",
  shortest: "Kürzeste Route",
  scenic: "Landschaftliche Route",
};

const avoidLabel: Record<string, string> = {
  highway: "Keine Autobahn",
  tolls: "Keine Maut",
  ferries: "Keine Fähren",
  unpaved: "Keine Schotterpisten",
};

const canApply = computed(() => {
  return geocoded.value?.destination != null;
});

async function listen() {
  error.value = "";
  try {
    const transcript = await startVoice();
    if (transcript) text.value = transcript;
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function geocodeText(q: string): Promise<SearchResult | null> {
  if (!q.trim()) return null;
  try {
    const resp = await fetch(
      `${searchUrl()}/api/search?q=${encodeURIComponent(q)}&limit=1`,
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.results?.[0] ?? null;
  } catch {
    return null;
  }
}

async function parse() {
  if (!text.value.trim()) return;
  parsing.value = true;
  error.value = "";
  parsed.value = null;
  geocoded.value = null;

  try {
    const resp = await fetch(`${backendUrl}/api/addons/navi_ai/parse`, {
      method: "POST",
      headers: {
        ...userStore.authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text: text.value }),
    });
    const body = await resp.json();
    if (!resp.ok) {
      error.value = body.error ?? "Unbekannter Fehler";
      return;
    }
    parsed.value = body;

    // Geocode destination and waypoints in parallel
    geocoding.value = true;
    const [destResult, ...wpResults] = await Promise.all([
      geocodeText(body.destination),
      ...(body.waypoints as string[]).map(geocodeText),
    ]);
    geocoded.value = {
      destination: destResult,
      waypoints: wpResults,
    };
    if (!destResult) {
      error.value = `Ziel "${body.destination}" konnte nicht auf der Karte gefunden werden.`;
    }
  } catch (e) {
    error.value = (e as Error).message || "Verbindungsfehler";
  } finally {
    parsing.value = false;
    geocoding.value = false;
  }
}

function apply() {
  if (!geocoded.value?.destination) return;
  emit("apply", {
    destination: geocoded.value.destination,
    waypoints: geocoded.value.waypoints.filter(Boolean) as SearchResult[],
    profile: parsed.value?.profile ?? "car",
    avoid: parsed.value?.avoid ?? [],
    routing_strategy: parsed.value?.routing_strategy ?? "fastest",
    notes: parsed.value?.notes ?? "",
  });
}

function reset() {
  parsed.value = null;
  geocoded.value = null;
  error.value = "";
}
</script>

<template>
  <div class="ai-input-panel">
    <div class="ai-header">
      <span class="ai-title">✨ KI-Navigation</span>
      <button class="ai-close" @click="emit('close')" title="Schließen">✕</button>
    </div>

    <div class="ai-body">
      <div class="ai-text-row">
        <textarea
          v-model="text"
          class="ai-textarea"
          placeholder="z.B. »Fahre mich zum Campingplatz Waldhort in Basel, aber keine Autobahn«"
          rows="2"
          @keydown.enter.ctrl.prevent="parse"
        />
        <button
          v-if="voiceSupported"
          class="mic-btn"
          :class="{ listening: isListening }"
          :disabled="parsing"
          @click="listen"
          title="Spracheingabe"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="9" y="2" width="6" height="11" rx="3"/>
            <path d="M5 10a7 7 0 0 0 14 0"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
            <line x1="9" y1="22" x2="15" y2="22"/>
          </svg>
        </button>
      </div>

      <button
        class="parse-btn"
        :disabled="!text.trim() || parsing || geocoding"
        @click="parse"
      >
        {{ parsing ? "Analysiere…" : geocoding ? "Geocodiere…" : "Route planen" }}
      </button>

      <p v-if="error" class="ai-error">{{ error }}</p>

      <!-- Parsed result chips -->
      <div v-if="parsed && !parsing" class="ai-result">
        <div class="result-chips">
          <span class="chip chip-dest" :class="{ 'chip-error': !geocoded?.destination }">
            🏁 {{ parsed.destination }}
          </span>
          <span v-for="wp in parsed.waypoints" :key="wp" class="chip chip-wp">
            📍 {{ wp }}
          </span>
          <span class="chip chip-profile">{{ profileLabel[parsed.profile] ?? parsed.profile }}</span>
          <span class="chip">{{ strategyLabel[parsed.routing_strategy] ?? parsed.routing_strategy }}</span>
          <span v-for="a in parsed.avoid" :key="a" class="chip chip-avoid">{{ avoidLabel[a] ?? a }}</span>
          <span v-if="parsed.prefer_scenic" class="chip chip-scenic">🌿 Landschaftlich</span>
        </div>
        <p v-if="parsed.notes" class="ai-notes">{{ parsed.notes }}</p>

        <div class="result-actions">
          <button class="reset-btn" @click="reset">Neu eingeben</button>
          <button
            class="apply-btn"
            :disabled="!canApply"
            @click="apply"
          >
            Übernehmen
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-input-panel {
  background: var(--bg-2);
  border: 1.5px solid var(--accent);
  border-radius: 12px;
  overflow: hidden;
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--accent-bg);
  border-bottom: 1px solid var(--accent);
}

.ai-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent-dark);
}

.ai-close {
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-3);
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s;
}
.ai-close:hover { color: #ef4444; }

.ai-body {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-text-row {
  display: flex;
  gap: 6px;
  align-items: flex-start;
}

.ai-textarea {
  flex: 1;
  padding: 8px 10px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg-input);
  color: var(--text-1);
  font-size: 13px;
  line-height: 1.45;
  resize: none;
  outline: none;
  font-family: inherit;
  transition: border-color 0.15s;
}
.ai-textarea:focus { border-color: var(--accent); }
.ai-textarea::placeholder { color: var(--text-4); }

.mic-btn {
  width: 38px;
  height: 38px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.mic-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.mic-btn.listening {
  border-color: #ef4444;
  color: #ef4444;
  animation: mic-pulse 1s ease-in-out infinite;
}
.mic-btn:disabled { opacity: 0.4; cursor: not-allowed; }

@keyframes mic-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.parse-btn {
  padding: 8px 16px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.parse-btn:hover:not(:disabled) { background: var(--accent-dark); }
.parse-btn:disabled { background: var(--border-2); color: var(--text-4); cursor: not-allowed; }

.ai-error {
  margin: 0;
  font-size: 12px;
  color: #ef4444;
  background: #fee2e2;
  border-radius: 6px;
  padding: 6px 8px;
}

/* Result display */
.ai-result {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 500;
  background: var(--bg-3);
  color: var(--text-2);
  border: 1px solid var(--border-1);
}
.chip-dest {
  background: var(--accent-bg);
  color: var(--accent-dark);
  border-color: var(--accent);
  font-weight: 600;
}
.chip-error {
  background: #fee2e2;
  color: #b91c1c;
  border-color: #f87171;
}
.chip-wp {
  background: #fff7ed;
  color: #c2410c;
  border-color: #fed7aa;
}
.chip-profile {
  background: #f0fdf4;
  color: #15803d;
  border-color: #bbf7d0;
}
.chip-avoid {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}
.chip-scenic {
  background: #f0fdf4;
  color: #166534;
  border-color: #bbf7d0;
}

.ai-notes {
  margin: 0;
  font-size: 11px;
  color: var(--text-3);
  font-style: italic;
  padding: 4px 6px;
  background: var(--bg-3);
  border-radius: 6px;
}

.result-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.reset-btn {
  padding: 5px 10px;
  border: 1px solid var(--border-2);
  border-radius: 7px;
  background: none;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  transition: all 0.15s;
}
.reset-btn:hover { border-color: var(--accent); color: var(--accent); }

.apply-btn {
  padding: 5px 14px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.apply-btn:hover:not(:disabled) { background: var(--accent-dark); }
.apply-btn:disabled { background: var(--border-2); color: var(--text-4); cursor: not-allowed; }
</style>
