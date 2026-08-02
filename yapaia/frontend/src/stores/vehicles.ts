import { defineStore } from "pinia";
import { ref } from "vue";
import { useUserStore } from "./user";

export interface Vehicle {
  id: string;
  name: string;
  type: string;
  fuel_type: string | null;  // e5 | e10 | diesel | lpg | electric | null
  height: number | null;
  width: number | null;
  length: number | null;
  weight: number | null;
  notes: string;
}

const _BACKEND = import.meta.env.VITE_BACKEND_URL || "";

export const useVehiclesStore = defineStore("vehicles", () => {
  const userStore = useUserStore();
  const items = ref<Vehicle[]>([]);

  async function load() {
    if (!userStore.isLoggedIn) {
      items.value = [];
      return;
    }
    try {
      const resp = await fetch(`${_BACKEND}/api/vehicles/`, {
        headers: userStore.authHeaders(),
      });
      if (resp.ok) items.value = await resp.json();
    } catch {
      // silent
    }
  }

  function reset() {
    items.value = [];
  }

  return { items, load, reset };
});
