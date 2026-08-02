<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useUserStore } from "../stores/user";
import { useFavoritesStore } from "../stores/favorites";
import { useAdminStore, type AdminUser } from "../stores/admin";
import { useMapStore } from "../stores/map";
import { usePreferencesStore } from "../stores/preferences";
import { useToastsStore } from "../stores/toasts";
import { useConfirmStore } from "../stores/confirm";
import { searchUrl } from "../services/serviceUrl";
import VehicleManager from "./VehicleManager.vue";
import PremiumLock from "./PremiumLock.vue";
import { useThemeStore } from "../stores/theme";
import { resetAllDraggablePositions } from "../composables/useDraggable";
import { useAddonsStore } from "../stores/addons";
import { useUiStore } from "../stores/ui";
import AddonsTab from "./AddonsTab.vue";
import InfoTab from "./InfoTab.vue";

const backendUrl = import.meta.env.VITE_BACKEND_URL || "";
const userStore = useUserStore();
const themeStore = useThemeStore();
const favStore = useFavoritesStore();
const addonsStore = useAddonsStore();
const uiStore = useUiStore();
const adminStore = useAdminStore();
const mapStore = useMapStore();
const prefStore = usePreferencesStore();
const toasts = useToastsStore();
const confirmStore = useConfirmStore();

type Tab = "profile" | "navigation" | "addons" | "data" | "info" | "admin";
const activeTab = ref<Tab>("profile");

const open = computed({
  get: () => uiStore.settingsOpen,
  set: (v) => { uiStore.settingsOpen = v; },
});

// Sub-panel for "Daten" tab — choose between favorites and vehicles
const dataPanel = ref<"favorites" | "vehicles">("favorites");

// Collapsible "Erweitert" sections
const expandGpsAdvanced = ref(false);
const expandAltBackend = ref(false);

// ── Server (Alt-Backend) Settings ───────────────────────────────────────
const altBackendUrl = ref("");
const serverTesting = ref(false);
const serverTestResult = ref<{ ok: boolean; detail: string } | null>(null);

watch(() => prefStore.data.alt_backend_url, (v) => {
  altBackendUrl.value = v ?? "";
}, { immediate: true });

function saveAltBackend() {
  const url = altBackendUrl.value.trim();
  prefStore.set("alt_backend_url", url || undefined);
  toasts.success(url ? "Alt-Server gespeichert" : "Alt-Server entfernt");
  serverTestResult.value = null;
}

async function testAltBackend() {
  const url = altBackendUrl.value.trim();
  if (!url) { serverTestResult.value = { ok: false, detail: "Keine URL eingegeben" }; return; }
  serverTesting.value = true;
  serverTestResult.value = null;
  try {
    const resp = await fetch(`${url.replace(/\/$/, "")}/health`, { signal: AbortSignal.timeout(5000) });
    const data = await resp.json().catch(() => ({}));
    serverTestResult.value = data.status === "ok"
      ? { ok: true, detail: "Verbindung erfolgreich — Routing + Suche aktiv ✓" }
      : { ok: false, detail: "Server antwortet, aber unbekanntes Format" };
  } catch {
    serverTestResult.value = { ok: false, detail: "Nicht erreichbar — URL und Netzwerk prüfen" };
  } finally {
    serverTesting.value = false;
  }
}

// ── Profile editing ────────────────────────────────────────────────────
const editingName = ref(false);
const newDisplayName = ref("");
const nameError = ref("");
const nameSaving = ref(false);

function startEditName() {
  newDisplayName.value = userStore.user?.display_name ?? "";
  editingName.value = true;
  nameError.value = "";
}

async function saveDisplayName() {
  if (!newDisplayName.value.trim()) { nameError.value = "Name darf nicht leer sein"; return; }
  nameSaving.value = true;
  nameError.value = "";
  const resp = await fetch(`${backendUrl}/api/auth/me`, {
    method: "PATCH",
    headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: newDisplayName.value.trim() }),
  }).catch(() => null);
  if (resp?.ok) {
    await userStore.fetchMe();
    editingName.value = false;
    toasts.success("Name gespeichert");
  } else {
    nameError.value = "Konnte nicht gespeichert werden";
  }
  nameSaving.value = false;
}

// ── Password editing ────────────────────────────────────────────────────
const editingPassword = ref(false);
const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const passwordError = ref("");
const passwordSaving = ref(false);

function startEditPassword() {
  currentPassword.value = "";
  newPassword.value = "";
  confirmPassword.value = "";
  editingPassword.value = true;
  passwordError.value = "";
}

async function savePassword() {
  if (newPassword.value.length < 8) { passwordError.value = "Passwort muss mindestens 8 Zeichen haben"; return; }
  if (newPassword.value !== confirmPassword.value) { passwordError.value = "Passwörter stimmen nicht überein"; return; }
  passwordSaving.value = true;
  passwordError.value = "";
  const body: Record<string, string> = { new_password: newPassword.value };
  if (currentPassword.value) body.current_password = currentPassword.value;
  const resp = await fetch(`${backendUrl}/api/auth/me`, {
    method: "PATCH",
    headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  if (resp?.ok) {
    await userStore.fetchMe();
    editingPassword.value = false;
    toasts.success("Passwort gespeichert");
  } else {
    const err = await resp?.json().catch(() => ({}));
    passwordError.value = err?.detail || "Konnte nicht gespeichert werden";
  }
  passwordSaving.value = false;
}

async function doLogout() {
  const ok = await confirmStore.ask({
    title: "Abmelden?",
    message: "Du musst Dich danach erneut anmelden.",
    confirmText: "Abmelden",
  });
  if (!ok) return;
  userStore.logout();
  open.value = false;
}

// ── Favorites management ───────────────────────────────────────────────
type FavEditTarget = "home" | "work" | "custom";
const editTarget = ref<FavEditTarget | null>(null);
const specialQuery = ref("");
const customLabel = ref("");
const specialResults = ref<{ label: string; lat: number; lon: number; type: string }[]>([]);
const specialLoading = ref(false);
let specialTimer: ReturnType<typeof setTimeout> | null = null;

function startEdit(which: FavEditTarget) {
  editTarget.value = which;
  specialQuery.value = "";
  customLabel.value = "";
  specialResults.value = [];
}

function cancelEdit() {
  editTarget.value = null;
  specialQuery.value = "";
  customLabel.value = "";
  specialResults.value = [];
}

async function searchSpecial(q: string) {
  if (specialTimer) clearTimeout(specialTimer);
  if (q.trim().length < 2) { specialResults.value = []; return; }
  specialTimer = setTimeout(async () => {
    specialLoading.value = true;
    try {
      const resp = await fetch(`${searchUrl()}/api/search?q=${encodeURIComponent(q)}&limit=5`);
      if (resp.ok) {
        const data = await resp.json();
        specialResults.value = data.results ?? [];
      }
    } finally {
      specialLoading.value = false;
    }
  }, 300);
}

function selectSpecialResult(r: { label: string; lat: number; lon: number; type: string }) {
  const target = editTarget.value;
  if (!target) return;
  if (target === "custom") {
    const label = customLabel.value.trim() || r.label;
    favStore.add(label, r);
  } else {
    favStore.setSpecial(target, r);
  }
  cancelEdit();
  toasts.success("Favorit gespeichert");
}

async function removeFavorite(id: string, label: string) {
  const ok = await confirmStore.ask({
    title: "Favorit löschen?",
    message: `„${label}" wird unwiderruflich entfernt.`,
    confirmText: "Löschen",
    danger: true,
  });
  if (!ok) return;
  await favStore.remove(id);
}

// ── GPS ────────────────────────────────────────────────────────────────
const gpsSources = [
  { key: "browser"  as const, label: "Gerät",     icon: "📱", desc: "GPS des anzeigenden Geräts (Browser)" },
  { key: "server"   as const, label: "USB-GPS",   icon: "🔌", desc: "Serieller GPS-Empfänger am Server" },
  { key: "url"      as const, label: "URL-Push",  icon: "🔗", desc: "Externe GPS-App oder Tracker" },
  { key: "simulate" as const, label: "Simulator", icon: "🎮", desc: "Fährt automatisch entlang der Route" },
];

const gpsPushUrl = computed(() => {
  const base = import.meta.env.VITE_BACKEND_URL || window.location.origin;
  const tok = userStore.user?.gps_push_token ?? "";
  return `${base}/api/gps/push?token=${tok}&lat={lat}&lon={lon}&speed={speed}&heading={heading}`;
});

const regeneratingToken = ref(false);

async function copyGpsUrl() {
  await navigator.clipboard.writeText(gpsPushUrl.value);
  toasts.success("Push-URL in Zwischenablage kopiert");
}

async function regenerateGpsToken() {
  const ok = await confirmStore.ask({
    title: "Neuen Token erzeugen?",
    message: "Bestehende Apps mit dem alten Token können danach keine GPS-Daten mehr senden.",
    confirmText: "Neu erzeugen",
    danger: true,
  });
  if (!ok) return;
  regeneratingToken.value = true;
  try {
    await userStore.regenerateGpsToken();
    toasts.success("Neuer Token erzeugt");
  } catch {
    toasts.error("Token konnte nicht regeneriert werden");
  } finally {
    regeneratingToken.value = false;
  }
}

function selectGpsSource(key: typeof gpsSources[number]["key"]) {
  mapStore.gpsSource = key;
  prefStore.set("gps_source", key);
}

// ── Admin ──────────────────────────────────────────────────────────────
function fmtDate(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

async function toggleAdminAction(u: AdminUser, patch: Partial<Pick<AdminUser, "plan" | "is_active" | "is_admin">>) {
  try {
    await adminStore.updateUser(u.id, patch);
    toasts.success("Benutzer aktualisiert");
  } catch (e) {
    toasts.error((e as Error).message);
  }
}

async function deleteUserAction(u: AdminUser) {
  const ok = await confirmStore.ask({
    title: "User löschen?",
    message: `„${u.email}" wird unwiderruflich entfernt — inklusive aller Fahrzeuge, Favoriten und Einstellungen.`,
    confirmText: "Endgültig löschen",
    danger: true,
  });
  if (!ok) return;
  try {
    await adminStore.deleteUser(u.id);
    toasts.success("Benutzer gelöscht");
  } catch (e) {
    toasts.error((e as Error).message);
  }
}

watch(activeTab, (tab) => {
  if (tab === "admin" && userStore.isAdmin) adminStore.loadUsers();
  if (tab === "addons") addonsStore.fetchInstalled();
});

function openModal() {
  uiStore.settingsOpen = true;
  addonsStore.fetchInstalled();
}

onMounted(() => addonsStore.fetchInstalled());
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="open = false">
      <div class="modal">
        <div class="modal-header">
          <h2>Einstellungen</h2>
          <button class="close-btn" @click="open = false">✕</button>
        </div>

        <div class="tabs">
          <button :class="{ active: activeTab === 'profile' }" @click="activeTab = 'profile'">Profil</button>
          <button :class="{ active: activeTab === 'navigation' }" @click="activeTab = 'navigation'">Karte &amp; Navigation</button>
          <button :class="{ active: activeTab === 'addons' }" @click="activeTab = 'addons'">🧩 Add-ons</button>
          <button :class="{ active: activeTab === 'data' }" @click="activeTab = 'data'">Daten</button>
          <button :class="{ active: activeTab === 'info' }" @click="activeTab = 'info'">ℹ Info</button>
          <button v-if="userStore.isAdmin" class="admin-tab" :class="{ active: activeTab === 'admin' }" @click="activeTab = 'admin'">Admin</button>
        </div>

        <!-- ══════════════════════════ PROFIL ══════════════════════════ -->
        <section v-if="activeTab === 'profile'">
          <div class="account-card">
            <div class="avatar">{{ (userStore.user?.display_name?.[0] ?? "?").toUpperCase() }}</div>
            <div class="account-info">
              <div v-if="!editingName" class="name-row">
                <strong>{{ userStore.user?.display_name }}</strong>
                <button class="edit-inline-btn" @click="startEditName" title="Name ändern">✏️</button>
              </div>
              <div v-else class="name-edit-row">
                <input v-model="newDisplayName" class="name-input" placeholder="Anzeigename" @keydown.enter.prevent="saveDisplayName" />
                <button class="btn-xs-primary" :disabled="nameSaving" @click="saveDisplayName">{{ nameSaving ? "…" : "✓" }}</button>
                <button class="btn-xs" @click="editingName = false">✕</button>
              </div>
              <p v-if="nameError" class="field-error">{{ nameError }}</p>
              <p class="email">{{ userStore.user?.email }}</p>
            </div>
          </div>

          <div class="plan-row">
            <div class="plan-row-info">
              <span class="plan-label">Abo</span>
              <span class="plan-badge" :class="userStore.isPremium ? 'premium' : 'free'">
                {{ userStore.isPremium ? "Premium" : "Free" }}
              </span>
            </div>
            <button v-if="!userStore.isPremium" class="upgrade-btn" disabled title="Upgrade-Pfad in Vorbereitung">
              Upgrade
            </button>
          </div>

          <div v-if="!userStore.isPremium" class="plan-hint">
            <PremiumLock /> Wohnmobil-Routing, unbegrenzte Fahrzeugprofile und mehr.
          </div>

          <div class="plan-row">
            <div class="plan-row-info">
              <span class="plan-label">Rolle</span>
              <span class="plan-badge" :class="userStore.isAdmin ? 'badge-admin' : 'badge-user'">
                {{ userStore.isAdmin ? "Administrator" : "Benutzer" }}
              </span>
            </div>
          </div>

          <!-- Passwort -->
          <div class="profile-section">
            <span class="plan-label">Passwort</span>
            <div v-if="!editingPassword" class="email-row">
              <span class="email-value">{{ userStore.user?.has_password ? "●●●●●●●● Gesetzt" : "Nicht gesetzt (Google-Konto)" }}</span>
              <button class="edit-inline-btn" @click="startEditPassword" :title="userStore.user?.has_password ? 'Passwort ändern' : 'Passwort setzen'">✏️</button>
            </div>
            <div v-else class="profile-edit-form">
              <input
                v-if="userStore.user?.has_password"
                v-model="currentPassword"
                type="password"
                placeholder="Aktuelles Passwort"
                autocomplete="current-password"
              />
              <input v-model="newPassword" type="password" placeholder="Neues Passwort (mind. 8 Zeichen)" autocomplete="new-password" />
              <input v-model="confirmPassword" type="password" placeholder="Passwort bestätigen" autocomplete="new-password" />
              <p v-if="passwordError" class="field-error">{{ passwordError }}</p>
              <div class="form-actions">
                <button class="btn-xs-primary" :disabled="passwordSaving" @click="savePassword">{{ passwordSaving ? "…" : "Speichern" }}</button>
                <button class="btn-xs" @click="editingPassword = false">Abbrechen</button>
              </div>
            </div>
          </div>

          <!-- Erscheinungsbild -->
          <div class="profile-section">
            <span class="plan-label">Erscheinungsbild</span>
            <div class="theme-row">
              <button class="theme-btn" :class="{ active: themeStore.mode === 'light' }" @click="themeStore.setMode('light')">
                <span class="t-icon">☀️</span>Hell
              </button>
              <button class="theme-btn" :class="{ active: themeStore.mode === 'system' }" @click="themeStore.setMode('system')">
                <span class="t-icon">⚙️</span>System
              </button>
              <button class="theme-btn" :class="{ active: themeStore.mode === 'dark' }" @click="themeStore.setMode('dark')">
                <span class="t-icon">🌙</span>Dunkel
              </button>
            </div>
          </div>

          <div class="action-row">
            <button class="logout-btn" @click="doLogout">Abmelden</button>
            <button class="reset-layout-btn" @click="resetAllDraggablePositions()" title="Alle verschobenen UI-Elemente zurücksetzen">
              Layout zurücksetzen
            </button>
          </div>
        </section>

        <!-- ══════════════════════ KARTE & NAVIGATION ═══════════════════ -->
        <section v-if="activeTab === 'navigation'">
          <!-- Sub-section: Sprachausgabe -->
          <div class="sub-block">
            <h3>Sprachausgabe</h3>
            <div class="tts-row">
              <div class="tts-label">
                <span>🔊 Abbiegeanweisungen sprechen</span>
                <small>Browser-TTS (Web Speech API)</small>
              </div>
              <label class="tts-switch">
                <input
                  type="checkbox"
                  :checked="prefStore.data.tts_enabled !== false"
                  @change="prefStore.set('tts_enabled', ($event.target as HTMLInputElement).checked)"
                />
                <span class="tts-slider"></span>
              </label>
            </div>
          </div>

          <!-- Sub-section: GPS -->
          <div class="sub-block">
            <h3>GPS-Quelle</h3>

            <div class="gps-chips">
              <button
                v-for="s in gpsSources"
                :key="s.key"
                class="gps-chip"
                :class="{
                  active: mapStore.gpsSource === s.key,
                  'gps-chip-disabled': s.key === 'simulate' && !mapStore.route,
                }"
                :disabled="s.key === 'simulate' && !mapStore.route"
                :title="s.key === 'simulate' && !mapStore.route ? 'Erst Route berechnen' : s.desc"
                @click="selectGpsSource(s.key)"
              >
                <span class="gps-chip-icon">{{ s.icon }}</span>
                <span class="gps-chip-label">{{ s.label }}</span>
              </button>
            </div>

            <p class="gps-selected-desc">
              <template v-if="mapStore.gpsSource === 'simulate' && !mapStore.route">
                Erst eine Route berechnen, dann Simulator starten.
              </template>
              <template v-else>
                {{ gpsSources.find(s => s.key === mapStore.gpsSource)?.desc }}
              </template>
            </p>

            <!-- Server GPS Info -->
            <div v-if="mapStore.gpsSource === 'server'" class="gps-info-box">
              <p>USB-GPS-Dongle muss am Server eingesteckt und in <code class="gps-inline">.env</code> konfiguriert sein:</p>
              <code class="gps-block-code">GPS_SERIAL_PORT=/dev/ttyUSB0</code>
            </div>

            <!-- Simulator Info -->
            <div v-if="mapStore.gpsSource === 'simulate'" class="gps-info-box gps-info-sim">
              <p>Der Simulator fährt die berechnete Route automatisch ab — nützlich zum Testen der Navigation.</p>
            </div>
          </div>

          <!-- Sub-section: Erweitert (collapsible) -->
          <button class="advanced-toggle" @click="expandGpsAdvanced = !expandGpsAdvanced">
            <span>{{ expandGpsAdvanced ? "▼" : "▶" }}</span>
            Erweitert · GPS-Push für externe Apps
          </button>

          <div v-if="expandGpsAdvanced" class="sub-block sub-advanced">
            <p class="hint">
              Push-URL für GPS-Logger (z.B. GPSLogger, OwnTracks). Die Platzhalter {lat}, {lon} etc.
              werden von GPS-Apps automatisch ersetzt.
            </p>
            <div class="gps-push-row">
              <code class="gps-push-code">{{ gpsPushUrl }}</code>
              <button class="copy-btn" @click="copyGpsUrl" title="In Zwischenablage kopieren">📋</button>
            </div>
            <p class="gps-info-hint">
              Der <code class="gps-inline">token</code>-Parameter ordnet die GPS-Daten Deinem Account zu — bitte privat halten.
            </p>
            <button class="regen-btn" :disabled="regeneratingToken" @click="regenerateGpsToken">
              {{ regeneratingToken ? "Generiere…" : "🔄 Neuen Token erzeugen" }}
            </button>
          </div>

          <!-- Sub-section: Alternativer Routing-Server -->
          <button class="advanced-toggle" @click="expandAltBackend = !expandAltBackend">
            <span>{{ expandAltBackend ? "▼" : "▶" }}</span>
            Erweitert · Alternativer Routing-Server
          </button>

          <div v-if="expandAltBackend" class="sub-block sub-advanced">
            <p class="hint">
              Eigene Navi-Instanz im Heimnetz (z.B. Raspberry Pi) für offline / schnelleres Routing.
            </p>

            <label>
              Server-URL
              <input
                v-model="altBackendUrl"
                type="url"
                placeholder="http://192.168.1.100:8001"
                autocomplete="off"
              />
            </label>

            <div v-if="prefStore.data.alt_backend_url" class="server-active-hint">
              ✓ Aktiv: Routing + Suche über <strong>{{ prefStore.data.alt_backend_url }}</strong>
            </div>

            <div v-if="serverTestResult" class="test-result" :class="serverTestResult.ok ? 'ok' : 'err'">
              {{ serverTestResult.detail }}
            </div>

            <div class="inline-actions">
              <button class="btn-secondary" :disabled="serverTesting" @click="testAltBackend">
                {{ serverTesting ? "Prüfe…" : "Verbindung testen" }}
              </button>
              <button class="btn-primary" @click="saveAltBackend">Speichern</button>
            </div>
          </div>
        </section>

        <!-- ══════════════════════════ ADD-ONS ════════════════════════ -->
        <section v-if="activeTab === 'addons'">
          <AddonsTab @close-modal="open = false" />
        </section>

        <!-- ════════════════════════════ INFO ═════════════════════════ -->
        <section v-if="activeTab === 'info'">
          <InfoTab />
        </section>

        <!-- ════════════════════════════ DATEN ═════════════════════════ -->
        <section v-if="activeTab === 'data'">
          <div class="data-switch">
            <button :class="{ active: dataPanel === 'favorites' }" @click="dataPanel = 'favorites'">⭐ Favoriten</button>
            <button :class="{ active: dataPanel === 'vehicles' }" @click="dataPanel = 'vehicles'">🚗 Fahrzeuge</button>
          </div>

          <!-- Favoriten -->
          <div v-if="dataPanel === 'favorites'">
            <!-- Home -->
            <div class="fav-special-row">
              <span class="fav-icon">🏠</span>
              <div class="fav-special-info">
                <strong>Zuhause</strong>
                <small v-if="favStore.home?.address" :title="favStore.home.address">{{ favStore.home.address }}</small>
                <small v-else-if="favStore.home" class="not-set">Adresse erneut setzen</small>
                <small v-else class="not-set">Noch nicht gesetzt</small>
              </div>
              <button
                v-if="favStore.home"
                class="fav-chip-toggle"
                :class="{ active: favStore.home.show_chip }"
                @click="favStore.toggleChip(favStore.home.id)"
                :title="favStore.home.show_chip ? 'Chip ausblenden' : 'Als Chip anzeigen'"
              >Chip</button>
              <button class="fav-action-btn" @click="startEdit('home')">
                {{ favStore.home ? "Ändern" : "Setzen" }}
              </button>
              <button v-if="favStore.home" class="fav-del-btn" @click="removeFavorite(favStore.home.id, 'Zuhause')" title="Löschen">🗑</button>
            </div>

            <div v-if="editTarget === 'home'" class="special-search">
              <input
                v-model="specialQuery"
                class="special-input"
                placeholder="Adresse suchen…"
                @input="searchSpecial(specialQuery)"
              />
              <ul v-if="specialResults.length" class="special-dropdown">
                <li v-for="r in specialResults" :key="r.label + r.lat" @click="selectSpecialResult(r)">
                  {{ r.label }}
                </li>
              </ul>
              <button class="sfp-cancel" @click="cancelEdit">Abbrechen</button>
            </div>

            <!-- Work -->
            <div class="fav-special-row">
              <span class="fav-icon">💼</span>
              <div class="fav-special-info">
                <strong>Arbeit</strong>
                <small v-if="favStore.work?.address" :title="favStore.work.address">{{ favStore.work.address }}</small>
                <small v-else-if="favStore.work" class="not-set">Adresse erneut setzen</small>
                <small v-else class="not-set">Noch nicht gesetzt</small>
              </div>
              <button
                v-if="favStore.work"
                class="fav-chip-toggle"
                :class="{ active: favStore.work.show_chip }"
                @click="favStore.toggleChip(favStore.work.id)"
                :title="favStore.work.show_chip ? 'Chip ausblenden' : 'Als Chip anzeigen'"
              >Chip</button>
              <button class="fav-action-btn" @click="startEdit('work')">
                {{ favStore.work ? "Ändern" : "Setzen" }}
              </button>
              <button v-if="favStore.work" class="fav-del-btn" @click="removeFavorite(favStore.work.id, 'Arbeit')" title="Löschen">🗑</button>
            </div>

            <div v-if="editTarget === 'work'" class="special-search">
              <input
                v-model="specialQuery"
                class="special-input"
                placeholder="Adresse suchen…"
                @input="searchSpecial(specialQuery)"
              />
              <ul v-if="specialResults.length" class="special-dropdown">
                <li v-for="r in specialResults" :key="r.label + r.lat" @click="selectSpecialResult(r)">
                  {{ r.label }}
                </li>
              </ul>
              <button class="sfp-cancel" @click="cancelEdit">Abbrechen</button>
            </div>

            <div class="fav-divider">
              <span>Gespeicherte Orte</span>
              <button v-if="editTarget !== 'custom'" class="fav-add-btn" @click="startEdit('custom')" title="Neuen Favoriten hinzufügen">+</button>
            </div>

            <div v-if="editTarget === 'custom'" class="special-search">
              <input
                v-model="customLabel"
                class="special-input"
                placeholder="Name (z.B. Oma, Sportverein) — optional"
              />
              <input
                v-model="specialQuery"
                class="special-input"
                placeholder="Adresse suchen…"
                @input="searchSpecial(specialQuery)"
              />
              <ul v-if="specialResults.length" class="special-dropdown">
                <li v-for="r in specialResults" :key="r.label + r.lat" @click="selectSpecialResult(r)">
                  {{ r.label }}
                </li>
              </ul>
              <button class="sfp-cancel" @click="cancelEdit">Abbrechen</button>
            </div>

            <div v-for="f in favStore.custom" :key="f.id" class="fav-custom-row">
              <span class="fav-icon">⭐</span>
              <div class="fav-special-info">
                <strong>{{ f.label }}</strong>
                <small v-if="f.address" :title="f.address">{{ f.address }}</small>
                <small v-else :title="`${f.lat.toFixed(5)}, ${f.lon.toFixed(5)}`">{{ f.lat.toFixed(4) }}, {{ f.lon.toFixed(4) }}</small>
              </div>
              <button
                class="fav-chip-toggle"
                :class="{ active: f.show_chip }"
                @click="favStore.toggleChip(f.id)"
                :title="f.show_chip ? 'Chip ausblenden' : 'Als Chip anzeigen'"
              >Chip</button>
              <button class="fav-del-btn" @click="removeFavorite(f.id, f.label)" title="Löschen">🗑</button>
            </div>

            <p v-if="!favStore.home && !favStore.work && !favStore.custom.length" class="empty-hint">
              Noch keine Favoriten. Setze Zuhause und Arbeit oben, lege eigene Orte über das + an,
              oder speichere Orte direkt aus der Suchleiste.
            </p>
          </div>

          <!-- Fahrzeuge -->
          <div v-if="dataPanel === 'vehicles'">
            <VehicleManager />
          </div>
        </section>

        <!-- ════════════════════════════ ADMIN ═════════════════════════ -->
        <section v-if="activeTab === 'admin' && userStore.isAdmin" class="admin-section">
          <div class="admin-header">
            <h3>Registrierte Benutzer ({{ adminStore.users.length }})</h3>
            <button class="btn-xs" :disabled="adminStore.loading" @click="adminStore.loadUsers()" title="Aktualisieren">↻</button>
          </div>

          <div v-if="adminStore.error" class="test-result err">{{ adminStore.error }}</div>

          <p v-if="adminStore.loading" class="hint">Lade…</p>
          <p v-else-if="!adminStore.users.length" class="empty-hint">Keine Benutzer.</p>

          <div v-for="u in adminStore.users" :key="u.id" class="admin-user-card">
            <div class="admin-user-head">
              <div class="admin-user-info">
                <strong>{{ u.display_name }}</strong>
                <small>{{ u.email }}</small>
                <small class="muted">Registriert: {{ fmtDate(u.created_at) }}</small>
              </div>
              <div class="admin-badges">
                <span v-if="u.id === userStore.user?.id" class="badge me">Du</span>
                <span v-if="!u.is_active" class="badge inactive">Deaktiviert</span>
                <span v-if="u.is_admin" class="badge admin">Admin</span>
                <span class="badge" :class="u.plan === 'premium' ? 'premium' : 'free'">{{ u.plan }}</span>
              </div>
            </div>

            <div class="admin-actions">
              <button class="btn-xs" @click="toggleAdminAction(u, { plan: u.plan === 'premium' ? 'free' : 'premium' })">
                {{ u.plan === 'premium' ? '↓ Free' : '↑ Premium' }}
              </button>
              <button v-if="u.id !== userStore.user?.id" class="btn-xs" @click="toggleAdminAction(u, { is_admin: !u.is_admin })">
                {{ u.is_admin ? 'Admin entziehen' : 'Admin geben' }}
              </button>
              <button v-if="u.id !== userStore.user?.id" class="btn-xs" @click="toggleAdminAction(u, { is_active: !u.is_active })">
                {{ u.is_active ? 'Deaktivieren' : 'Aktivieren' }}
              </button>
              <button v-if="u.id !== userStore.user?.id" class="btn-xs danger" @click="deleteUserAction(u)" title="User samt Daten löschen">
                🗑 Löschen
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.modal {
  background: var(--bg);
  border-radius: 16px;
  width: 100%;
  max-width: 460px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-1);
  position: sticky;
  top: 0;
  background: var(--bg);
  z-index: 1;
}

h2 { margin: 0; font-size: 18px; color: var(--text-1); }
h3 { margin: 0 0 6px; font-size: 14px; font-weight: 600; color: var(--text-2); }

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-1);
  overflow-x: auto;
}

.tabs button {
  flex: 1;
  padding: 10px 8px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-3);
  cursor: pointer;
  white-space: nowrap;
}

.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); }
.tabs button.admin-tab { color: #7c3aed; border-left: 1px solid var(--border-1); }
.tabs button.admin-tab.active { color: #6d28d9; border-bottom-color: #7c3aed; }

section {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sub-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--bg-2);
  border-radius: 10px;
  border: 1px solid var(--border-1);
}

.sub-block h3 { margin: 0; }
.sub-block.sub-advanced { background: #fffbeb; border-color: #fde68a; }

.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px dashed var(--border-2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  cursor: pointer;
  text-align: left;
}

.advanced-toggle:hover { background: var(--bg-2); color: var(--text-2); }
.advanced-toggle span { font-size: 10px; }

/* ── Data sub-switch ───────────────────────────────────────────────── */
.data-switch {
  display: flex;
  gap: 4px;
  padding: 3px;
  background: var(--bg-3);
  border-radius: 10px;
}

.data-switch button {
  flex: 1;
  padding: 8px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
  cursor: pointer;
  transition: background 0.15s;
}

.data-switch button.active {
  background: var(--bg);
  color: var(--text-1);
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* ── Profile ───────────────────────────────────────────────────────── */
.account-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--bg-2);
  border-radius: 10px;
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.account-info { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.name-row { display: flex; align-items: center; gap: 6px; }
.name-row strong { font-size: 15px; }

.edit-inline-btn {
  background: none;
  border: none;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  opacity: 0.6;
  color: var(--text-2);
}
.edit-inline-btn:hover { opacity: 1; }

.name-edit-row { display: flex; align-items: center; gap: 4px; }

.name-input {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  color: var(--text-1);
  background: var(--bg-input);
}

.name-input:focus { border-color: var(--accent); }

.btn-xs-primary {
  padding: 4px 8px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 600;
}
.btn-xs-primary:disabled { background: var(--text-4); cursor: not-allowed; }

.btn-xs {
  padding: 4px 8px;
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-3);
}

.email { margin: 0; font-size: 12px; color: var(--text-4); }
.field-error { margin: 0; font-size: 11px; color: #ef4444; }

.plan-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: var(--bg-2);
  border-radius: 10px;
}

.plan-row-info { display: flex; align-items: center; gap: 10px; }

.plan-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.plan-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 700;
}

.plan-badge.free { background: #fef3c7; color: #92400e; }
.plan-badge.premium { background: #dbeafe; color: #1e40af; }
.plan-badge.badge-admin { background: #e0e7ff; color: #3730a3; }
.plan-badge.badge-user { background: var(--bg-3); color: var(--text-2); }

.upgrade-btn {
  padding: 5px 12px;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  opacity: 0.6;
}

.plan-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: -6px 0 0;
  padding: 8px 12px;
  font-size: 12px;
  color: #78350f;
  background: #fffbeb;
  border-radius: 8px;
  line-height: 1.4;
}

.logout-btn {
  padding: 8px 16px;
  background: #fee2e2;
  color: #991b1b;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
}

/* ── Favorites ─────────────────────────────────────────────────────── */
.fav-special-row, .fav-custom-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-2);
  border-radius: 8px;
  margin-bottom: 6px;
}

.fav-icon { font-size: 20px; flex-shrink: 0; }

.fav-special-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.fav-special-info strong { font-size: 13px; color: var(--text-1); }
.fav-special-info small { font-size: 11px; color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fav-special-info .not-set { color: var(--text-4); font-style: italic; }

.fav-action-btn {
  padding: 4px 10px;
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  flex-shrink: 0;
}
.fav-action-btn:hover { border-color: var(--accent); color: var(--accent-text); }

.server-active-hint {
  margin: 8px 0;
  padding: 8px 12px;
  background: #dcfce7;
  color: #166534;
  border-radius: 8px;
  font-size: 12px;
  word-break: break-all;
}

.fav-chip-toggle {
  flex-shrink: 0;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 20px;
  border: 1.5px solid var(--border-2);
  background: var(--bg-3);
  color: var(--text-4);
  cursor: pointer;
  transition: all 0.15s;
}
.fav-chip-toggle.active { background: var(--accent-bg-2); border-color: var(--accent); color: var(--accent-text); }
.fav-chip-toggle:hover { opacity: 0.8; }

.fav-del-btn {
  background: none;
  border: none;
  font-size: 15px;
  cursor: pointer;
  opacity: 0.5;
  flex-shrink: 0;
  padding: 2px;
  color: var(--text-2);
}
.fav-del-btn:hover { opacity: 1; }

.special-search {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  margin-bottom: 6px;
  background: var(--accent-bg);
  border-radius: 8px;
  border: 1px solid var(--accent-border);
}

.special-input {
  padding: 7px 10px;
  border: 1px solid var(--accent-border);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-1);
  outline: none;
  background: var(--bg-input);
}
.special-input:focus { border-color: var(--accent); }

.special-dropdown {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--bg);
  border: 1px solid var(--border-1);
  border-radius: 6px;
  max-height: 160px;
  overflow-y: auto;
}

.special-dropdown li {
  padding: 7px 10px;
  font-size: 12px;
  color: var(--text-2);
  cursor: pointer;
  border-bottom: 1px solid var(--border-3);
}
.special-dropdown li:hover { background: var(--accent-bg); }
.special-dropdown li:last-child { border-bottom: none; }

.sfp-cancel {
  padding: 5px 12px;
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 7px;
  font-size: 12px;
  color: var(--text-3);
  cursor: pointer;
  align-self: flex-start;
}

.fav-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-4);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 14px 0 6px;
}

.fav-divider::before, .fav-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-1);
}

.fav-add-btn {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.fav-add-btn:hover { background: var(--accent-dark); }

.empty-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-4);
  line-height: 1.6;
  text-align: center;
  padding: 12px;
}

/* ── Common form ───────────────────────────────────────────────────── */
.hint { margin: 0; font-size: 12px; color: var(--text-3); line-height: 1.5; }

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-2);
}

input {
  padding: 8px 10px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-1);
  background: var(--bg-input);
  outline: none;
}
input:focus { border-color: var(--accent); }

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

.test-result {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
}
.test-result.ok { background: #dcfce7; color: #166534; }
.test-result.err { background: #fee2e2; color: #991b1b; }

.inline-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 4px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--text-4);
}

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
.btn-secondary:disabled { color: var(--text-4); cursor: not-allowed; }

/* ── Admin ─────────────────────────────────────────────────────────── */
.admin-section { background: var(--bg-2); }

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.admin-user-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg);
  border-radius: 8px;
  border: 1px solid var(--border-1);
}

.admin-user-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.admin-user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.admin-user-info strong { font-size: 14px; color: var(--text-1); }

.admin-user-info small {
  font-size: 11px;
  color: var(--text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.admin-user-info small.muted { color: var(--text-4); }

.admin-badges { display: flex; flex-wrap: wrap; gap: 4px; flex-shrink: 0; }

.badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 99px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.badge.free { background: #fef3c7; color: #92400e; }
.badge.premium { background: #dbeafe; color: #1e40af; }
.badge.admin { background: #e0e7ff; color: #3730a3; }
.badge.me { background: #d1fae5; color: #065f46; }
.badge.inactive { background: #fee2e2; color: #991b1b; }

.admin-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.admin-actions .btn-xs { padding: 4px 10px; font-size: 11px; }

.btn-xs.danger {
  background: #fee2e2;
  color: #991b1b;
  border-color: #fecaca;
}
.btn-xs.danger:hover { background: #fecaca; }

/* ── GPS source chips ───────────────────────────────────────────────── */
.gps-chips {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.gps-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 10px 8px;
  border: 1.5px solid var(--border-2);
  border-radius: 10px;
  background: var(--bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.gps-chip:hover:not(:disabled) { border-color: var(--accent); background: var(--accent-bg); }
.gps-chip.active {
  border-color: var(--accent);
  background: var(--accent-bg);
  box-shadow: 0 0 0 2px var(--accent);
}
.gps-chip.gps-chip-disabled { opacity: 0.4; cursor: not-allowed; }

.gps-chip-icon { font-size: 26px; line-height: 1; }
.gps-chip-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  letter-spacing: 0.01em;
}
.gps-chip.active .gps-chip-label { color: var(--accent-text); }

.gps-selected-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.4;
}

.gps-info-box {
  padding: 12px;
  background: var(--bg-2);
  border-radius: 8px;
  border: 1px solid var(--border-1);
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gps-info-box p { margin: 0; }
.gps-info-hint { font-size: 11px; color: var(--text-4); }

.regen-btn {
  margin-top: 4px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  color: #b45309;
  background: var(--bg);
  border: 1px solid #fcd34d;
  border-radius: 6px;
  cursor: pointer;
  align-self: flex-start;
}
.regen-btn:hover:not(:disabled) { background: #fde68a; }
.regen-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.gps-push-row { display: flex; align-items: center; gap: 6px; }

.gps-push-code {
  flex: 1;
  font-size: 10px;
  background: var(--bg-input);
  padding: 5px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-2);
  word-break: break-all;
  line-height: 1.4;
  color: var(--text-2);
}

.copy-btn {
  background: var(--bg);
  border: 1px solid var(--border-2);
  border-radius: 6px;
  padding: 5px 9px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-2);
}
.copy-btn:hover { background: var(--bg-2); }

.gps-inline {
  background: var(--bg);
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid var(--border-2);
  font-size: 11px;
}

.gps-block-code {
  display: block;
  background: var(--bg);
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid var(--border-2);
  font-size: 11px;
  color: var(--accent);
}

.gps-info-sim {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}

/* ── TTS Toggle ────────────────────────────────────────────────────── */
.tts-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
}

.tts-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.tts-label small { font-size: 11px; font-weight: 400; color: var(--text-4); }

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



/* ── Action row (Abmelden + Layout-Reset) ─────────────────────────────── */
.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.reset-layout-btn {
  padding: 8px 14px;
  background: none;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-3);
  cursor: pointer;
}
.reset-layout-btn:hover { background: var(--bg-2); color: var(--text-2); }

/* ── Profile sections (E-Mail / Passwort) ─────────────────────────────── */
.profile-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.email-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.email-value {
  font-size: 13px;
  color: var(--text-1);
}

.profile-edit-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--bg-2);
  border-radius: 8px;
  border: 1px solid var(--border-1);
}

.form-actions {
  display: flex;
  gap: 6px;
  margin-top: 2px;
}

/* ── Theme selector ─────────────────────────────────────────────────────── */
.theme-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.theme-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1.5px solid var(--border-2);
  border-radius: 8px;
  background: var(--bg);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  transition: all 0.15s;
}
.theme-btn:hover { border-color: var(--accent); color: var(--accent-text); }
.theme-btn.active { border-color: var(--accent); background: var(--accent-bg); color: var(--accent-text); }
.t-icon { font-size: 16px; }

/* ── Tankstellen settings ────────────────────────────────────────────────── */
.api-key-hint {
  background: #fef9c3;
  border: 1px solid #fde047;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 13px;
}
.api-key-hint strong { display: block; margin-bottom: 6px; }
.block-code {
  display: block;
  background: var(--bg-3);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  margin-top: 6px;
  word-break: break-all;
}

.stations-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-1);
  margin-bottom: 12px;
}
.stations-toggle-label { display: flex; flex-direction: column; gap: 2px; font-size: 14px; }
.stations-toggle-label small { font-size: 11px; color: var(--text-3); }

.stations-section { margin-bottom: 14px; }
.stations-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-2); margin-bottom: 6px; }

.fuel-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.fuel-chip {
  padding: 5px 12px;
  border: 1.5px solid var(--border-2);
  border-radius: 99px;
  background: var(--bg);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  transition: all 0.15s;
}
.fuel-chip.active { border-color: var(--accent); background: var(--accent-bg); color: var(--accent-text); }
.fuel-chip:hover:not(.active) { border-color: var(--accent-border); }

.radius-row { display: flex; align-items: center; gap: 10px; }
.radius-slider { flex: 1; accent-color: var(--accent); }
.radius-val { font-size: 13px; font-weight: 600; color: var(--text-1); min-width: 36px; text-align: right; }

.stations-info {
  background: var(--bg-2);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.6;
}
.stations-info p { margin: 0 0 4px; }
.stations-info p:last-child { margin-bottom: 0; }

</style>
