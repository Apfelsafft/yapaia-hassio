<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useUserStore } from "../stores/user";

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const GITHUB_REPO = "https://github.com/Apfelsafft/yapaia-hassio";

const userStore = useUserStore();

interface BackendInfo {
  version: string;
  start_time: string;
  python_version: string;
}

const backendInfo = ref<BackendInfo | null>(null);
const backendError = ref(false);

const frontendBuildTime = __BUILD_TIME__;

// Issue form
const issueType = ref<"bug" | "feature">("bug");
const issueTitle = ref("");
const issueBody = ref("");

async function fetchBackendInfo() {
  try {
    const resp = await fetch(`${_BACKEND}/api/info`, {
      headers: userStore.authHeaders(),
    });
    if (resp.ok) backendInfo.value = await resp.json();
    else backendError.value = true;
  } catch {
    backendError.value = true;
  }
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function openIssue() {
  if (!issueTitle.value.trim()) return;
  const label = issueType.value === "bug" ? "bug" : "enhancement";
  const body = [
    issueBody.value.trim(),
    "",
    "---",
    `**Navi Version:** ${backendInfo.value?.version ?? "?"}`,
    `**Frontend Build:** ${fmtTime(frontendBuildTime)}`,
    `**Backend Start:** ${backendInfo.value ? fmtTime(backendInfo.value.start_time) : "?"}`,
  ].join("\n");

  const url = new URL(`${GITHUB_REPO}/issues/new`);
  url.searchParams.set("title", issueTitle.value.trim());
  url.searchParams.set("body", body);
  url.searchParams.set("labels", label);
  window.open(url.toString(), "_blank", "noopener");
}

onMounted(fetchBackendInfo);
</script>

<template>
  <div class="info-tab">
    <!-- ── Branding ────────────────────────────────────────────────── -->
    <div class="brand-header">
      <img src="/Yapaia_icon.png" alt="Yapaia" class="brand-icon" />
      <div class="brand-text">
        <span class="brand-name">Yapaia Go</span>
        <span class="brand-sub">Smart RV Solutions</span>
      </div>
    </div>

    <!-- ── Build Info ──────────────────────────────────────────────── -->
    <div class="section-title">🔧 System</div>

    <div class="info-table">
      <div class="info-row">
        <span class="info-label">Frontend</span>
        <span class="info-val">gebaut {{ fmtTime(frontendBuildTime) }}</span>
      </div>

      <template v-if="backendInfo">
        <div class="info-row">
          <span class="info-label">Backend</span>
          <span class="info-val">v{{ backendInfo.version }} · gestartet {{ fmtTime(backendInfo.start_time) }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Python</span>
          <span class="info-val">{{ backendInfo.python_version }}</span>
        </div>
      </template>
      <div v-else-if="backendError" class="info-row">
        <span class="info-label">Backend</span>
        <span class="info-val err">nicht erreichbar</span>
      </div>
      <div v-else class="info-row">
        <span class="info-label">Backend</span>
        <span class="info-val muted">lade…</span>
      </div>
    </div>

    <a :href="GITHUB_REPO" target="_blank" rel="noopener" class="repo-link">
      GitHub Repository ↗
    </a>

    <!-- ── Issue Reporter ─────────────────────────────────────────── -->
    <div class="section-title" style="margin-top: 20px;">🐛 Fehler / Feature melden</div>

    <div class="type-chips">
      <button
        class="type-chip"
        :class="{ active: issueType === 'bug' }"
        @click="issueType = 'bug'"
      >🐛 Fehler</button>
      <button
        class="type-chip"
        :class="{ active: issueType === 'feature' }"
        @click="issueType = 'feature'"
      >✨ Feature</button>
    </div>

    <div class="form-field">
      <label class="field-label">Titel *</label>
      <input
        v-model="issueTitle"
        type="text"
        class="field-input"
        :placeholder="issueType === 'bug' ? 'z.B. Navigation friert bei Reroute ein' : 'z.B. Höhenprofil entlang der Route'"
        maxlength="120"
      />
    </div>

    <div class="form-field">
      <label class="field-label">Beschreibung <span class="muted">(optional)</span></label>
      <textarea
        v-model="issueBody"
        class="field-input field-textarea"
        :placeholder="issueType === 'bug'
          ? 'Schritte um den Fehler zu reproduzieren:\n1. …\n2. …\n\nErwartetes Verhalten:\nTatsächliches Verhalten:'
          : 'Was soll diese Funktion können?\nWozu wird sie genutzt?'"
        rows="5"
      />
    </div>

    <button
      class="btn-submit"
      :disabled="!issueTitle.trim()"
      @click="openIssue"
    >
      Auf GitHub melden ↗
    </button>

    <p class="submit-hint">
      Öffnet GitHub — du benötigst einen GitHub-Account um das Issue abzusenden.
    </p>
  </div>
</template>

<style scoped>
.info-tab { display: flex; flex-direction: column; gap: 10px; }

.brand-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 8px;
}

.brand-icon {
  width: 56px;
  height: 56px;
  object-fit: contain;
  border-radius: 12px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1;
}

.brand-sub {
  font-size: 11px;
  color: var(--text-3);
  font-weight: 500;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-2);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-1);
}

.info-table { display: flex; flex-direction: column; gap: 6px; }

.info-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
}

.info-label {
  flex-shrink: 0;
  width: 80px;
  font-weight: 600;
  color: var(--text-3);
}

.info-val { color: var(--text-1); }
.info-val.err { color: #ef4444; }
.info-val.muted { color: var(--text-4); font-style: italic; }

.repo-link {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  display: inline-block;
  margin-top: 2px;
}
.repo-link:hover { text-decoration: underline; }

.type-chips {
  display: flex;
  gap: 8px;
}

.type-chip {
  flex: 1;
  padding: 7px;
  border: 1.5px solid var(--border-2);
  border-radius: 10px;
  background: var(--bg);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  cursor: pointer;
}
.type-chip.active {
  background: var(--accent-bg);
  border-color: var(--accent);
  color: var(--accent);
}

.form-field { display: flex; flex-direction: column; gap: 4px; }

.field-label { font-size: 12px; font-weight: 600; color: var(--text-2); }

.field-input {
  padding: 8px 10px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-1);
  background: var(--bg-input);
  font-family: inherit;
  outline: none;
  resize: vertical;
}
.field-input:focus { border-color: var(--accent); }

.field-textarea { resize: vertical; min-height: 90px; line-height: 1.5; }

.btn-submit {
  padding: 9px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 2px;
}
.btn-submit:disabled { background: var(--text-4); cursor: not-allowed; }
.btn-submit:not(:disabled):hover { background: var(--accent-dark); }

.submit-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-4);
  line-height: 1.4;
}

.muted { color: var(--text-4); font-weight: 400; }
</style>
