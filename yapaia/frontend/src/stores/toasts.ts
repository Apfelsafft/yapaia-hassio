import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "info" | "success" | "error";

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

export const useToastsStore = defineStore("toasts", () => {
  const items = ref<Toast[]>([]);
  let nextId = 1;

  function push(message: string, kind: ToastKind = "info", timeoutMs = 3000) {
    const id = nextId++;
    items.value = [...items.value, { id, message, kind }];
    if (timeoutMs > 0) {
      setTimeout(() => dismiss(id), timeoutMs);
    }
    return id;
  }

  function dismiss(id: number) {
    items.value = items.value.filter(t => t.id !== id);
  }

  return {
    items,
    dismiss,
    push,
    info:    (msg: string, ms?: number) => push(msg, "info", ms),
    success: (msg: string, ms?: number) => push(msg, "success", ms),
    error:   (msg: string, ms?: number) => push(msg, "error", ms ?? 5000),
  };
});
