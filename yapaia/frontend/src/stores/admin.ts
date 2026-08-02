import { defineStore } from "pinia";
import { ref } from "vue";
import { useUserStore } from "./user";

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  plan: "free" | "premium";
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

export const useAdminStore = defineStore("admin", () => {
  const userStore = useUserStore();
  const users = ref<AdminUser[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadUsers() {
    if (!userStore.isAdmin) return;
    loading.value = true;
    error.value = null;
    try {
      const resp = await fetch(`${_BACKEND}/api/admin/users`, { headers: userStore.authHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      users.value = await resp.json();
    } catch (e) {
      error.value = (e as Error).message;
    } finally {
      loading.value = false;
    }
  }

  async function updateUser(id: string, patch: Partial<Pick<AdminUser, "plan" | "is_active" | "is_admin">>) {
    const resp = await fetch(`${_BACKEND}/api/admin/users/${id}`, {
      method: "PATCH",
      headers: { ...userStore.authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const updated: AdminUser = await resp.json();
    const idx = users.value.findIndex((u) => u.id === id);
    if (idx >= 0) users.value.splice(idx, 1, updated);
  }

  async function deleteUser(id: string) {
    const resp = await fetch(`${_BACKEND}/api/admin/users/${id}`, {
      method: "DELETE",
      headers: userStore.authHeaders(),
    });
    if (!resp.ok && resp.status !== 404) {
      const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    users.value = users.value.filter((u) => u.id !== id);
  }

  return { users, loading, error, loadUsers, updateUser, deleteUser };
});
