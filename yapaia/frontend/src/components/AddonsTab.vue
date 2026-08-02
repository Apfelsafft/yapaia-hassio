<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useAddonsStore, type AddonManifest, type SettingsField } from "../stores/addons";
import { useUserStore } from "../stores/user";
import { useToastsStore } from "../stores/toasts";
import TrackRecorderView from "./TrackRecorderView.vue";
import MapStyleView from "./MapStyleView.vue";

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const emit = defineEmits<{ (e: "close-modal"): void }>();

const addonsStore = useAddonsStore();
const userStore = useUserStore();
const toasts = useToastsStore();

type View = "list" | "settings" | "marketplace" | "tracks" | "mapstyle";
const view = ref<View>("list");
const activeAddon = ref<AddonManifest | null>(null);
const localSettings = ref<Record<string, unknown>>({});
const saving = ref(false);
const showPasswords = ref<Record<string, boolean>>({});

// Marketplace install with license key
const installLicenseKey = ref("");
const showLicenseInput = ref<string | null>(null);

// Uninstall confirmation
const confirmUninstall = ref<string | null>(null);

// ── Computed ───────────────────────────────────────────────────────────────
const notInstalled = computed(() =>
  addonsStore.catalog.filter((c) => !addonsStore.isInstalled(c.id))
);

// ── Marketplace ────────────────────────────────────────────────────────────
async function openMarketplace() {
  view.value = "marketplace";
  await addonsStore.fetchCatalog();
}

function requestInstall(id: string, requiresLicense: boolean) {
  if (requiresLicense) {
    showLicenseInput.value = id;
    installLicenseKey.value = "";
  } else {
    doInstall(id, undefined);
  }
}

async function doInstall(id: string, licenseKey: string | undefined) {
  showLicenseInput.value = null;
  const result = await addonsStore.install(id, licenseKey);
  if (result.ok) {
    toasts.success("Add-on installiert");
    view.value = "list";
  } else {
    toasts.error(result.message);
  }
}

// ── Uninstall ──────────────────────────────────────────────────────────────
async function doUninstall(id: string) {
  confirmUninstall.value = null;
  const result = await addonsStore.uninstall(id);
  if (result.ok) {
    toasts.success("Add-on deinstalliert");
    if (activeAddon.value?.id === id) view.value = "list";
  } else {
    toasts.error(result.message);
  }
}

// ── Settings form ──────────────────────────────────────────────────────────
async function openSettings(addon: AddonManifest) {
  activeAddon.value = addon;
  await addonsStore.fetchSettings(addon.id);
  const saved = addonsStore.getAddonSettings(addon.id);
  const form: Record<string, unknown> = {};
  for (const field of addon.settings_schema) {
    form[field.key] = saved[field.key] ?? field.default ?? defaultForType(field);
  }
  localSettings.value = form;
  showPasswords.value = {};
  view.value = "settings";
}

function defaultForType(field: SettingsField): unknown {
  if (field.type === "boolean") return false;
  if (field.type === "number" || field.type === "range") return field.min ?? 0;
  return "";
}

async function saveAddonSettings() {
  if (!activeAddon.value) return;
  saving.value = true;
  const ok = await addonsStore.saveSettings(activeAddon.value.id, localSettings.value);
  saving.value = false;
  if (ok) toasts.success("Einstellungen gespeichert");
  else toasts.error("Speichern fehlgeschlagen");
}

function togglePassword(key: string) {
  showPasswords.value[key] = !showPasswords.value[key];
}

// ── HA connection test ─────────────────────────────────────────────────────
const haTestResult = ref<{ ok: boolean; detail: string } | null>(null);
const haTestLoading = ref(false);

async function testHaConnection() {
  haTestLoading.value = true;
  haTestResult.value = null;
  const resp = await fetch(`${_BACKEND}/api/addons/home_assistant/test`, {
    headers: userStore.authHeaders(),
  }).catch(() => null);
  if (!resp) {
    haTestResult.value = { ok: false, detail: "Backend nicht erreichbar" };
  } else {
    haTestResult.value = await resp.json();
  }
  haTestLoading.value = false;
}

// ── Track Recorder shortcut ────────────────────────────────────────────────
function openTracks(addon: AddonManifest) {
  activeAddon.value = addon;
  view.value = "tracks";
}

// ── Map Style shortcut ─────────────────────────────────────────────────────
function openMapStyle(addon: AddonManifest) {
  activeAddon.value = addon;
  view.value = "mapstyle";
}

onMounted(() => addonsStore.fetchInstalled());
</script>

<template>
  <!-- ══════════════════════ INSTALLED LIST VIEW ══════════════════════════ -->
  <div v-if="view === 'list'" class="addons-view">
    <div class="addons-header">
      <h3 class="addons-title">Installierte Add-ons</h3>
      <button class="btn-marketplace" @click="openMarketplace">
        🛒 Marketplace
      </button>
    </div>

    <p v-if="!addonsStore.installed.length" class="empty-hint">
      Keine Add-ons installiert. Öffne den Marketplace, um Add-ons zu entdecken.
    </p>

    <div v-for="addon in addonsStore.installed" :key="addon.id" class="addon-card">
      <div class="addon-card-top">
        <span class="addon-icon">{{ addon.icon }}</span>
        <div class="addon-info">
          <div class="addon-name-row">
            <strong>{{ addon.name }}</strong>
            <span v-if="addon.license_status && addon.license_status !== 'free'" class="license-badge"
              :class="addon.license_status">
              {{ addon.license_status === 'valid' ? '✓ Lizenz' : addon.license_status === 'expired' ? '⚠ Abgelaufen' : '? Unverifiziert' }}
            </span>
          </div>
          <small>v{{ addon.version }} · {{ addon.author }}</small>
          <p v-if="addon.code_missing" class="addon-warn">⚠ Add-on-Code nicht auf Server geladen</p>
          <p v-else class="addon-desc">{{ addon.description }}</p>
        </div>
      </div>
      <div class="addon-btns">
        <button
          v-if="addon.id === 'mapstyle'"
          class="btn-configure"
          @click="openMapStyle(addon)"
        >🗺️ Kartenstile wählen</button>
        <button
          v-else-if="addon.settings_schema.length > 0 || addon.id === 'track_recorder'"
          class="btn-configure"
          @click="openSettings(addon)"
        >
          {{ addon.id === 'track_recorder' ? '🗺 Tracks & Einstellungen' : 'Einstellungen' }}
        </button>
        <!-- Uninstall -->
        <template v-if="confirmUninstall !== addon.id">
          <button
            class="btn-uninstall"
            :disabled="addonsStore.loadingUninstall === addon.id"
            @click="confirmUninstall = addon.id"
          >
            {{ addonsStore.loadingUninstall === addon.id ? "Deinstalliere…" : "Deinstallieren" }}
          </button>
        </template>
        <div v-else class="confirm-row">
          <span class="confirm-text">Wirklich deinstallieren?</span>
          <button class="btn-confirm-yes" @click="doUninstall(addon.id)">Ja</button>
          <button class="btn-confirm-no" @click="confirmUninstall = null">Nein</button>
        </div>
      </div><!-- addon-btns -->
    </div><!-- addon-card -->
  </div>

  <!-- ══════════════════════ SETTINGS FORM VIEW ══════════════════════════ -->
  <div v-else-if="view === 'settings' && activeAddon" class="addons-view">
    <div class="back-header">
      <button class="btn-back" @click="view = 'list'">← Zurück</button>
      <span class="back-title">{{ activeAddon.icon }} {{ activeAddon.name }}</span>
    </div>

    <p class="hint">{{ activeAddon.description }}</p>

    <div class="settings-form">
      <div
        v-for="field in activeAddon.settings_schema"
        :key="field.key"
        class="form-field"
      >
        <label class="field-label">
          {{ field.label }}
          <span v-if="field.required" class="required">*</span>
        </label>
        <p v-if="field.description" class="field-desc">{{ field.description }}</p>

        <!-- boolean / toggle -->
        <div v-if="field.type === 'boolean'" class="toggle-row">
          <label class="tts-switch">
            <input
              type="checkbox"
              :checked="!!localSettings[field.key]"
              @change="localSettings[field.key] = ($event.target as HTMLInputElement).checked"
            />
            <span class="tts-slider"></span>
          </label>
          <span class="toggle-label">{{ localSettings[field.key] ? "Aktiviert" : "Deaktiviert" }}</span>
        </div>

        <!-- password -->
        <div v-else-if="field.type === 'password'" class="token-row">
          <input
            :type="showPasswords[field.key] ? 'text' : 'password'"
            :value="String(localSettings[field.key] ?? '')"
            :placeholder="field.placeholder || ''"
            autocomplete="new-password"
            @input="localSettings[field.key] = ($event.target as HTMLInputElement).value"
          />
          <button class="toggle-btn" @click="togglePassword(field.key)" tabindex="-1">
            {{ showPasswords[field.key] ? "🙈" : "👁" }}
          </button>
        </div>

        <!-- select -->
        <select
          v-else-if="field.type === 'select'"
          :value="String(localSettings[field.key] ?? field.default ?? '')"
          @change="localSettings[field.key] = ($event.target as HTMLSelectElement).value"
        >
          <option v-for="opt in field.options" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <!-- range -->
        <div v-else-if="field.type === 'range'" class="range-row">
          <input
            type="range"
            :min="field.min ?? 0"
            :max="field.max ?? 100"
            :step="field.step ?? 1"
            :value="Number(localSettings[field.key] ?? field.default ?? field.min ?? 0)"
            @input="localSettings[field.key] = Number(($event.target as HTMLInputElement).value)"
            class="range-slider"
          />
          <span class="range-val">{{ localSettings[field.key] ?? field.default }}</span>
        </div>

        <!-- number -->
        <input
          v-else-if="field.type === 'number'"
          type="number"
          :min="field.min"
          :max="field.max"
          :step="field.step ?? 1"
          :value="Number(localSettings[field.key] ?? field.default ?? 0)"
          @input="localSettings[field.key] = Number(($event.target as HTMLInputElement).value)"
        />

        <!-- text (default) -->
        <input
          v-else
          type="text"
          :value="String(localSettings[field.key] ?? '')"
          :placeholder="field.placeholder || ''"
          @input="localSettings[field.key] = ($event.target as HTMLInputElement).value"
        />
      </div>
    </div>

    <!-- HA-specific test button -->
    <div v-if="activeAddon.id === 'home_assistant'" class="ha-test-row">
      <div v-if="haTestResult" class="test-result" :class="haTestResult.ok ? 'ok' : 'err'">
        {{ haTestResult.detail }}
      </div>
      <button class="btn-secondary" :disabled="haTestLoading" @click="testHaConnection">
        {{ haTestLoading ? "Teste…" : "Verbindung testen" }}
      </button>
    </div>

    <div class="form-actions">
      <button class="btn-primary" :disabled="saving" @click="saveAddonSettings">
        {{ saving ? "Speichere…" : "Speichern" }}
      </button>
      <button class="btn-secondary" @click="view = 'list'">Abbrechen</button>
    </div>

    <!-- Track Recorder: zeige Track-Liste direkt unter den Einstellungen -->
    <template v-if="activeAddon.id === 'track_recorder'">
      <div class="section-divider">🗺️ Aufgezeichnete Tracks</div>
      <TrackRecorderView @close-modal="emit('close-modal')" />
    </template>
  </div>

  <!-- ════════════════════ MAP STYLE PICKER VIEW ═══════════════════════ -->
  <div v-else-if="view === 'mapstyle' && activeAddon" class="addons-view">
    <div class="back-header">
      <button class="btn-back" @click="view = 'list'">← Zurück</button>
      <span class="back-title">{{ activeAddon.icon }} {{ activeAddon.name }}</span>
    </div>
    <MapStyleView />
  </div>

  <!-- ══════════════════════ MARKETPLACE VIEW ════════════════════════════ -->
  <div v-else-if="view === 'marketplace'" class="addons-view">
    <div class="back-header">
      <button class="btn-back" @click="view = 'list'">← Zurück</button>
      <span class="back-title">🛒 Marketplace</span>
    </div>

    <p v-if="addonsStore.catalogLoading" class="hint">Lade Marketplace…</p>

    <div v-else-if="!addonsStore.catalog.length" class="empty-hint">
      Marketplace nicht erreichbar.
    </div>

    <template v-else>
      <div v-if="addonsStore.installed.length" class="section-label">Installiert</div>
      <div
        v-for="addon in addonsStore.installed"
        :key="addon.id"
        class="addon-card installed-card"
      >
        <span class="addon-icon">{{ addon.icon }}</span>
        <div class="addon-info">
          <strong>{{ addon.name }}</strong>
          <small>v{{ addon.version }}</small>
        </div>
        <span class="badge-installed">✓ Installiert</span>
      </div>

      <div v-if="notInstalled.length" class="section-label">Verfügbar</div>
      <p v-else-if="!notInstalled.length && addonsStore.installed.length" class="hint">
        Alle verfügbaren Add-ons sind bereits installiert.
      </p>

      <div v-for="entry in notInstalled" :key="entry.id" class="addon-card">
        <span class="addon-icon">{{ entry.icon }}</span>
        <div class="addon-info">
          <strong>{{ entry.name }}</strong>
          <small>v{{ entry.version }} · {{ entry.author }}</small>
          <p class="addon-desc">{{ entry.description }}</p>
          <span v-if="entry.price && entry.price > 0" class="price-badge">
            💶 {{ entry.price.toFixed(2) }} €
          </span>
          <span v-else class="price-badge free">Kostenlos</span>
        </div>

        <!-- License key input (paid) -->
        <div v-if="showLicenseInput === entry.id" class="license-input-col">
          <input
            v-model="installLicenseKey"
            type="text"
            placeholder="Lizenzschlüssel eingeben…"
            class="license-input"
            @keydown.enter="doInstall(entry.id, installLicenseKey)"
          />
          <div class="license-btns">
            <button class="btn-install" @click="doInstall(entry.id, installLicenseKey)">
              Aktivieren
            </button>
            <button class="btn-secondary-sm" @click="showLicenseInput = null">Abbrechen</button>
          </div>
        </div>

        <button
          v-else
          class="btn-install"
          :disabled="addonsStore.loadingInstall === entry.id"
          @click="requestInstall(entry.id, !!entry.requires_license)"
        >
          {{ addonsStore.loadingInstall === entry.id ? "…" : entry.requires_license ? "🔑 Lizenz eingeben" : "Installieren" }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.addons-view { display: flex; flex-direction: column; gap: 12px; }

.addons-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.addons-title { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-2); }

.btn-marketplace {
  padding: 6px 14px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.addon-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--bg-2);
  border: 1px solid var(--border-1);
  border-radius: 10px;
}

.addon-card-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.installed-card { opacity: 0.7; }

.addon-icon { font-size: 28px; flex-shrink: 0; line-height: 1; margin-top: 2px; }

.addon-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.addon-name-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.addon-info strong { font-size: 14px; color: var(--text-1); }
.addon-info small { font-size: 11px; color: var(--text-3); }
.addon-desc { margin: 4px 0 0; font-size: 12px; color: var(--text-3); line-height: 1.4; }
.addon-warn { margin: 4px 0 0; font-size: 11px; color: #b45309; }

.addon-btns {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.btn-configure {
  padding: 5px 10px;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  cursor: pointer;
  white-space: nowrap;
}
.btn-configure:hover { border-color: var(--accent); color: var(--accent-text); }

.btn-uninstall {
  padding: 6px 12px;
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  cursor: pointer;
  width: 100%;
}
.btn-uninstall:hover { border-color: #ef4444; color: #ef4444; background: rgba(239,68,68,0.05); }
.btn-uninstall:disabled { opacity: 0.4; cursor: not-allowed; }

.confirm-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.confirm-text { font-size: 11px; color: var(--text-3); }
.btn-confirm-yes {
  padding: 3px 8px;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}
.btn-confirm-no {
  padding: 3px 8px;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  color: var(--text-2);
}

.license-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 99px;
  white-space: nowrap;
}
.license-badge.valid { background: #dcfce7; color: #166534; }
.license-badge.expired { background: #fee2e2; color: #991b1b; }
.license-badge.unverified { background: #fef9c3; color: #854d0e; }

.btn-install {
  flex-shrink: 0;
  padding: 6px 14px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  align-self: flex-start;
}
.btn-install:disabled { background: var(--text-4); cursor: not-allowed; }

.badge-installed {
  flex-shrink: 0;
  padding: 4px 10px;
  background: #dcfce7;
  color: #166534;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.price-badge {
  display: inline-block;
  margin-top: 4px;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 99px;
  background: #fef3c7;
  color: #92400e;
}
.price-badge.free { background: #dcfce7; color: #166534; }

.license-input-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 180px;
}
.license-input {
  padding: 6px 8px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-1);
  background: var(--bg-input);
}
.license-btns { display: flex; gap: 4px; }
.btn-secondary-sm {
  padding: 4px 8px;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  color: var(--text-2);
}

.section-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-1);
}

.section-divider {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-2);
  padding: 12px 0 4px;
  border-top: 1px solid var(--border-1);
  margin-top: 4px;
}

/* ── Back header ────────────────────────────────────────────────────────── */
.back-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.btn-back {
  background: none;
  border: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
}

.back-title { font-size: 14px; font-weight: 600; color: var(--text-1); flex: 1; }

.btn-settings-link {
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  width: 30px; height: 30px;
  font-size: 15px;
  cursor: pointer;
  color: var(--text-3);
}
.btn-settings-link:hover { border-color: var(--accent); }

/* ── Settings form ─────────────────────────────────────────────────────── */
.settings-form { display: flex; flex-direction: column; gap: 14px; }

.form-field { display: flex; flex-direction: column; gap: 4px; }

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}

.required { color: #ef4444; margin-left: 2px; }

.field-desc { margin: 0; font-size: 11px; color: var(--text-3); line-height: 1.4; }

.form-field input[type="text"],
.form-field input[type="password"],
.form-field input[type="number"],
.form-field select {
  padding: 8px 10px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-1);
  background: var(--bg-input);
  outline: none;
}
.form-field input:focus,
.form-field select:focus { border-color: var(--accent); }

.token-row { display: flex; gap: 6px; }
.token-row input { flex: 1; }

.toggle-btn {
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-2);
}

.toggle-row { display: flex; align-items: center; gap: 10px; }
.toggle-label { font-size: 13px; color: var(--text-2); }

.range-row { display: flex; align-items: center; gap: 10px; }
.range-slider { flex: 1; accent-color: var(--accent); }
.range-val { font-size: 13px; font-weight: 600; color: var(--text-1); min-width: 36px; text-align: right; }

.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 8px;
}

.ha-test-row { margin-top: -4px; }

.btn-primary {
  padding: 8px 18px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { background: var(--text-4); cursor: not-allowed; }

.btn-secondary {
  padding: 8px 18px;
  background: var(--bg);
  color: var(--text-2);
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.hint { margin: 0; font-size: 12px; color: var(--text-3); line-height: 1.5; }

.empty-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-4);
  text-align: center;
  padding: 16px;
  line-height: 1.6;
}

.test-result {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
}
.test-result.ok { background: #dcfce7; color: #166534; }
.test-result.err { background: #fee2e2; color: #991b1b; }

.tts-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}
.tts-switch input { opacity: 0; width: 0; height: 0; }
.tts-slider {
  position: absolute;
  inset: 0;
  background: #d1d5db;
  border-radius: 99px;
  cursor: pointer;
  transition: background 0.2s;
}
.tts-slider::before {
  content: "";
  position: absolute;
  width: 18px;
  height: 18px;
  left: 3px;
  top: 3px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
}
.tts-switch input:checked + .tts-slider { background: #3b82f6; }
.tts-switch input:checked + .tts-slider::before { transform: translateX(20px); }
</style>
