import { defineStore } from "pinia";
import { ref, computed } from "vue";

export type ThemeMode = "system" | "light" | "dark";

export const useThemeStore = defineStore("theme", () => {
  const mode = ref<ThemeMode>("system");

  const mql = window.matchMedia("(prefers-color-scheme: dark)");
  const systemIsDark = ref(mql.matches);

  const isDark = computed(
    () => mode.value === "dark" || (mode.value === "system" && systemIsDark.value)
  );

  function _applyToDOM(m: ThemeMode) {
    document.documentElement.dataset.theme = isDark.value ? "dark" : "light";
  }

  function setMode(m: ThemeMode) {
    mode.value = m;
    _applyToDOM(m);
    try { localStorage.setItem("navi_theme", m); } catch { /* ignore */ }
  }

  function init() {
    const saved = localStorage.getItem("navi_theme") as ThemeMode | null;
    mode.value = saved ?? "system";
    _applyToDOM(mode.value);
  }

  // React to OS dark/light switch when mode is "system"
  mql.addEventListener("change", (e) => {
    systemIsDark.value = e.matches;
    if (mode.value === "system") _applyToDOM("system");
  });

  // HA can call this to override the theme temporarily
  function applyExternal(m: "dark" | "light") {
    mode.value = m;
    document.documentElement.dataset.theme = m;
  }

  return { mode, isDark, setMode, init, applyExternal };
});
