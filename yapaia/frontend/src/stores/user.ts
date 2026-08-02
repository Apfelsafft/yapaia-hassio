import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  plan: "free" | "premium";
  is_admin: boolean;
  gps_push_token: string | null;
  has_password: boolean;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";
const _TOKEN_KEY = "navi_token";

export const useUserStore = defineStore("user", () => {
  const user = ref<UserProfile | null>(null);
  const token = ref<string>(localStorage.getItem(_TOKEN_KEY) || "");

  const isLoggedIn = computed(() => !!user.value);
  const isPremium = computed(() => user.value?.plan === "premium");
  const isAdmin = computed(() => user.value?.is_admin === true);

  function authHeaders(): Record<string, string> {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {};
  }

  async function fetchMe() {
    if (!token.value) return;
    const resp = await fetch(`${_BACKEND}/api/auth/me`, { headers: authHeaders() });
    if (resp.ok) {
      user.value = await resp.json();
    } else {
      logout();
    }
  }

  async function login(email: string, password: string): Promise<string | null> {
    const form = new URLSearchParams({ username: email, password });
    const resp = await fetch(`${_BACKEND}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!resp.ok) {
      const err = await resp.json();
      return err.detail || "Anmeldung fehlgeschlagen";
    }
    const data = await resp.json();
    token.value = data.access_token;
    localStorage.setItem(_TOKEN_KEY, token.value);
    await fetchMe();
    return null;
  }

  async function register(
    email: string,
    password: string,
    displayName: string
  ): Promise<string | null> {
    const resp = await fetch(`${_BACKEND}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      return err.detail || "Registrierung fehlgeschlagen";
    }
    return login(email, password);
  }

  function logout() {
    user.value = null;
    token.value = "";
    localStorage.removeItem(_TOKEN_KEY);
  }

  async function loginWithToken(t: string): Promise<void> {
    token.value = t;
    localStorage.setItem(_TOKEN_KEY, t);
    await fetchMe();
  }

  async function regenerateGpsToken(): Promise<void> {
    const resp = await fetch(`${_BACKEND}/api/auth/gps-token/regenerate`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (resp.ok) user.value = await resp.json();
  }

  fetchMe();

  return { user, token, isLoggedIn, isPremium, isAdmin, authHeaders, login, register, logout, fetchMe, loginWithToken, regenerateGpsToken };
});
