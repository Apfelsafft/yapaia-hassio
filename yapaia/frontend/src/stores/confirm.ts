import { defineStore } from "pinia";
import { ref } from "vue";

export interface ConfirmOptions {
  title: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

export const useConfirmStore = defineStore("confirm", () => {
  const active = ref<ConfirmOptions | null>(null);
  let resolver: ((ok: boolean) => void) | null = null;

  /** Open the confirm dialog and wait for the user's choice. */
  function ask(opts: ConfirmOptions): Promise<boolean> {
    // If something is already open, auto-deny the previous one so we don't leak resolvers.
    if (resolver) resolver(false);
    active.value = opts;
    return new Promise(res => { resolver = res; });
  }

  function answer(ok: boolean) {
    const r = resolver;
    resolver = null;
    active.value = null;
    r?.(ok);
  }

  return { active, ask, answer };
});
