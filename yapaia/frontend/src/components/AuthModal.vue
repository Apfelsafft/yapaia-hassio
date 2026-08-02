<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useUserStore } from "../stores/user";

const backendUrl = import.meta.env.VITE_BACKEND_URL || "";
const store = useUserStore();
const mode = ref<"login" | "register">("login");
const email = ref("");
const password = ref("");
const displayName = ref("");
const error = ref("");
const loading = ref(false);
const googleEnabled = ref(false);

onMounted(async () => {
  const resp = await fetch(`${backendUrl}/api/auth/providers`).catch(() => null);
  if (resp?.ok) {
    const data = await resp.json();
    googleEnabled.value = data.google ?? false;
  }
});

function loginWithGoogle() {
  window.location.href = `${backendUrl}/api/auth/google`;
}

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    const err =
      mode.value === "login"
        ? await store.login(email.value, password.value)
        : await store.register(email.value, password.value, displayName.value);
    if (err) error.value = err;
  } catch (e: any) {
    error.value = e?.message || "Netzwerkfehler — Backend nicht erreichbar?";
  } finally {
    loading.value = false;
  }
}

function switchMode() {
  mode.value = mode.value === "login" ? "register" : "login";
  error.value = "";
}
</script>

<template>
  <div class="auth-overlay">
    <div class="auth-card">
      <div class="logo">
        <img src="/Yapaia_logo_crop.png" alt="Yapaia Go" class="logo-img" />
      </div>
      <h1>{{ mode === "login" ? "Anmelden" : "Konto erstellen" }}</h1>

      <form @submit.prevent="submit">
        <label v-if="mode === 'register'">
          Name
          <input v-model="displayName" type="text" placeholder="Max Mustermann" required />
        </label>

        <label>
          E-Mail
          <input v-model="email" type="email" placeholder="max@example.com" required />
        </label>

        <label>
          Passwort
          <input v-model="password" type="password" placeholder="Mindestens 8 Zeichen" required />
        </label>

        <p v-if="error" class="error">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? "…" : mode === "login" ? "Anmelden" : "Registrieren" }}
        </button>
      </form>

      <div v-if="googleEnabled" class="divider"><span>oder</span></div>

      <button v-if="googleEnabled" type="button" class="btn-google" @click="loginWithGoogle">
        <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        </svg>
        Mit Google anmelden
      </button>

      <p class="switch">
        {{ mode === "login" ? "Noch kein Konto?" : "Bereits registriert?" }}
        <a href="#" @click.prevent="switchMode">
          {{ mode === "login" ? "Jetzt registrieren" : "Anmelden" }}
        </a>
      </p>

      <div v-if="mode === 'register'" class="plan-info">
        <p><strong>Free:</strong> Karte, Routing, Navigation (1 Fahrzeug)</p>
        <p><strong>Premium:</strong> Wohnmobil-Profile, mehrere Fahrzeuge, Abmessungen</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-overlay {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #1e3a5f 0%, #1f2937 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 200;
}

.auth-card {
  background: var(--bg);
  border-radius: 20px;
  padding: 32px 28px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.4);
}

.logo {
  text-align: center;
  margin-bottom: 4px;
}

.logo-img {
  width: 100%;
  max-width: 280px;
  height: auto;
  object-fit: contain;
}

h1 {
  margin: 0 0 24px;
  text-align: center;
  font-size: 22px;
  color: var(--text-1);
}

form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-2);
}

input {
  padding: 10px 12px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  background: var(--bg-input);
  color: var(--text-1);
}

input:focus {
  border-color: var(--accent);
}

.error {
  margin: 0;
  font-size: 13px;
  color: #dc2626;
  text-align: center;
}

button[type="submit"] {
  padding: 12px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}

button[type="submit"]:disabled {
  background: var(--text-4);
  cursor: not-allowed;
}

.switch {
  margin: 18px 0 0;
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
}

.switch a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
}

.divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0 4px;
  color: var(--text-4);
  font-size: 12px;
}
.divider::before, .divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-1);
}

.btn-google {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 11px;
  background: var(--bg);
  color: var(--text-2);
  border: 1.5px solid var(--border-2);
  border-radius: 10px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}
.btn-google:hover {
  background: var(--bg-2);
  border-color: var(--text-4);
}

.plan-info {
  margin-top: 18px;
  padding: 12px;
  background: var(--bg-2);
  border-radius: 10px;
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.7;
}

.plan-info p {
  margin: 0;
}
</style>
