<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useUserStore } from "../stores/user";
import { useVehiclesStore, type Vehicle } from "../stores/vehicles";
import { usePreferencesStore } from "../stores/preferences";
import { useConfirmStore } from "../stores/confirm";
import { useToastsStore } from "../stores/toasts";

const userStore = useUserStore();
const vehiclesStore = useVehiclesStore();
const prefStore = usePreferencesStore();
const confirmStore = useConfirmStore();
const toasts = useToastsStore();
const backendUrl = import.meta.env.VITE_BACKEND_URL || "";

const editing = ref<Partial<Vehicle> | null>(null);
const saving = ref(false);
const error = ref("");

const vehicles = computed(() => vehiclesStore.items);
const defaultVehicleId = computed(() => prefStore.data.default_vehicle_id || "");

const TYPES = [
  { value: "car",        label: "PKW" },
  { value: "motorcycle", label: "Motorrad" },
  { value: "motorhome",  label: "Wohnmobil" },
  { value: "bike",       label: "Fahrrad" },
];

const FUEL_TYPES = [
  { value: "", label: "Nicht angegeben" },
  { value: "e5", label: "Super E5" },
  { value: "e10", label: "Super E10" },
  { value: "diesel", label: "Diesel" },
  { value: "lpg", label: "Autogas (LPG)" },
  { value: "electric", label: "Elektrisch" },
];

function setDefault(id: string) {
  if (defaultVehicleId.value === id) {
    prefStore.set("default_vehicle_id", "");
  } else {
    prefStore.set("default_vehicle_id", id);
    const v = vehiclesStore.items.find(x => x.id === id);
    if (v) prefStore.set("default_profile", v.type as "car" | "motorhome" | "bike" | "foot" | "motorcycle");
  }
}

function startAdd() {
  editing.value = { name: "", type: "car", fuel_type: null, height: null, width: null, length: null, weight: null, notes: "" };
  error.value = "";
}

function startEdit(v: Vehicle) {
  editing.value = { ...v };
  error.value = "";
}

function cancelEdit() {
  editing.value = null;
}

async function saveVehicle() {
  if (!editing.value) return;
  saving.value = true;
  error.value = "";
  const isNew = !editing.value.id;
  const url = isNew ? `${backendUrl}/api/vehicles/` : `${backendUrl}/api/vehicles/${editing.value.id}`;
  const resp = await fetch(url, {
    method: isNew ? "POST" : "PUT",
    headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(editing.value),
  });
  if (!resp.ok) {
    const err = await resp.json();
    error.value = err.detail || "Fehler beim Speichern";
  } else {
    editing.value = null;
    await vehiclesStore.load();
  }
  saving.value = false;
}

async function deleteVehicle(id: string, name: string) {
  const ok = await confirmStore.ask({
    title: "Fahrzeug löschen?",
    message: `„${name}" wird entfernt.`,
    confirmText: "Löschen",
    danger: true,
  });
  if (!ok) return;
  const resp = await fetch(`${backendUrl}/api/vehicles/${id}`, {
    method: "DELETE",
    headers: userStore.authHeaders(),
  });
  if (resp.ok) toasts.success("Fahrzeug gelöscht");
  else toasts.error("Löschen fehlgeschlagen");
  if (defaultVehicleId.value === id) prefStore.set("default_vehicle_id", "");
  await vehiclesStore.load();
}

onMounted(() => vehiclesStore.load());
</script>

<template>
  <div class="vm">
    <div class="vm-header">
      <h3>Meine Fahrzeuge</h3>
      <span v-if="!userStore.isPremium" class="badge-free">Free: 1 Fahrzeug</span>
      <button class="add-btn" @click="startAdd">+ Hinzufügen</button>
    </div>

    <ul class="vehicle-list">
      <li v-for="v in vehicles" :key="v.id" class="vehicle-item">
        <span class="v-icon">{{
          v.type === "motorhome" ? "🚐" :
          v.type === "motorcycle" ? "🏍️" :
          v.type === "bike" ? "🚲" : "🚗"
        }}</span>
        <div class="v-info">
          <strong>{{ v.name }}</strong>
          <small>
            {{ [
              v.fuel_type && FUEL_TYPES.find(f => f.value === v.fuel_type)?.label,
              v.height && `H: ${v.height}m`,
              v.weight && `${v.weight}t`
            ].filter(Boolean).join(" · ") || "" }}
          </small>
        </div>
        <button
          class="icon-btn star-btn"
          :class="{ starred: defaultVehicleId === v.id }"
          @click="setDefault(v.id)"
          :title="defaultVehicleId === v.id ? 'Standard entfernen' : 'Als Standard setzen'"
        >{{ defaultVehicleId === v.id ? "★" : "☆" }}</button>
        <button class="icon-btn" @click="startEdit(v)">✏️</button>
        <button class="icon-btn" @click="deleteVehicle(v.id, v.name)">🗑</button>
      </li>
      <li v-if="vehicles.length === 0" class="empty">Noch keine Fahrzeuge</li>
    </ul>

    <!-- Edit / Add Form -->
    <div v-if="editing" class="edit-form">
      <h4>{{ editing.id ? "Fahrzeug bearbeiten" : "Fahrzeug hinzufügen" }}</h4>

      <label>Name <input v-model="editing.name" placeholder="Mein Wohnmobil" /></label>
      <label>
        Typ
        <select v-model="editing.type">
          <option v-for="t in TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </label>

      <label>
        Kraftstoff
        <select v-model="editing.fuel_type">
          <option v-for="f in FUEL_TYPES" :key="f.value" :value="f.value || null">{{ f.label }}</option>
        </select>
      </label>

      <template v-if="editing.type === 'motorhome' || editing.type === 'car'">
        <div class="dim-grid">
          <label>Höhe (m) <input v-model.number="editing.height" type="number" step="0.1" placeholder="3.5" /></label>
          <label>Breite (m) <input v-model.number="editing.width" type="number" step="0.1" placeholder="2.3" /></label>
          <label>Länge (m) <input v-model.number="editing.length" type="number" step="0.1" placeholder="7.5" /></label>
          <label>Gew. (t) <input v-model.number="editing.weight" type="number" step="0.5" placeholder="3.5" /></label>
        </div>
        <p class="dim-hint">
          Abmessungen werden beim Routing berücksichtigt (Höhenbeschränkungen, Gewichtslimits).
          <span v-if="!userStore.isPremium" class="premium-hint">Für Wohnmobil-Routing <strong>Premium</strong> erforderlich.</span>
        </p>
      </template>

      <label>Notizen <input v-model="editing.notes" placeholder="Kennzeichen, Versicherung …" /></label>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="form-actions">
        <button class="btn-secondary" @click="cancelEdit">Abbrechen</button>
        <button class="btn-primary" :disabled="saving" @click="saveVehicle">
          {{ saving ? "Speichere…" : "Speichern" }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vm { display: flex; flex-direction: column; gap: 12px; }

.vm-header { display: flex; align-items: center; gap: 8px; }
h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-2); flex: 1; }
h4 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text-1); }

.badge-free {
  font-size: 11px; background: #fef3c7; color: #92400e;
  padding: 2px 8px; border-radius: 99px; font-weight: 500;
}

.add-btn {
  padding: 5px 12px; background: var(--accent); color: white;
  border: none; border-radius: 6px; font-size: 13px;
  font-weight: 600; cursor: pointer;
}

.vehicle-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }

.vehicle-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; background: var(--bg-2);
  border-radius: 8px; font-size: 13px;
}

.v-icon { font-size: 20px; }
.v-info { flex: 1; display: flex; flex-direction: column; }
.v-info small { color: var(--text-3); font-size: 11px; }
.icon-btn { background: none; border: none; cursor: pointer; font-size: 15px; padding: 2px; }

.star-btn { color: var(--border-2); font-size: 17px; transition: color 0.15s; }
.star-btn:hover { color: #f59e0b; }
.star-btn.starred { color: #f59e0b; }

.empty { font-size: 13px; color: var(--text-4); text-align: center; padding: 8px; }

.edit-form {
  padding: 14px; background: var(--bg-2);
  border-radius: 10px; display: flex; flex-direction: column; gap: 10px;
}

label {
  display: flex; flex-direction: column; gap: 3px;
  font-size: 12px; font-weight: 500; color: var(--text-2);
}

input, select {
  padding: 7px 9px; border: 1px solid var(--border-2);
  border-radius: 6px; font-size: 13px; outline: none;
  color: var(--text-1); background-color: var(--bg-input);
}

input:focus, select:focus { border-color: var(--accent); }

.dim-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

.dim-hint {
  margin: 0; font-size: 11px; color: var(--text-3); line-height: 1.5;
}

.premium-hint { color: #d97706; }

.error { margin: 0; font-size: 12px; color: #dc2626; }

.form-actions { display: flex; gap: 8px; justify-content: flex-end; }

.btn-primary {
  padding: 7px 16px; background: var(--accent); color: white;
  border: none; border-radius: 7px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.btn-primary:disabled { background: var(--text-4); cursor: not-allowed; }
.btn-secondary {
  padding: 7px 16px; background: var(--bg); color: var(--text-2);
  border: 1px solid var(--border-2); border-radius: 7px; font-size: 13px;
  font-weight: 600; cursor: pointer;
}
</style>
