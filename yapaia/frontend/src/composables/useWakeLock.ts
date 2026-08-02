import { ref, onUnmounted } from "vue";

// Screen Wake Lock — verhindert Bildschirm-Abdunkelung während Navigation.
// Der Lock wird vom Browser automatisch freigegeben wenn die Seite in den
// Hintergrund wechselt (Tab-Wechsel, Sperrbildschirm) — wir fordern ihn
// beim nächsten Sichtbarwerden erneut an, solange Navigation aktiv ist.

export function useWakeLock() {
  const sentinel = ref<WakeLockSentinel | null>(null);
  let active = false;

  async function acquire() {
    if (!("wakeLock" in navigator)) return;
    if (!active) return;
    if (document.visibilityState !== "visible") return;
    try {
      const s = await navigator.wakeLock.request("screen");
      sentinel.value = s;
      // Wenn der Browser den Lock freigibt (Seite versteckt): Marker behalten
      // damit wir ihn beim nächsten Sichtbarwerden neu anfordern
      s.addEventListener("release", () => {
        sentinel.value = null;
      });
    } catch {
      // Kein Wake Lock verfügbar (ältere Browser, falsche Rechte) — kein Problem
    }
  }

  function release() {
    sentinel.value?.release().catch(() => {});
    sentinel.value = null;
  }

  async function onVisibilityChange() {
    if (document.visibilityState === "visible" && active && !sentinel.value) {
      await acquire();
    }
  }

  function start() {
    active = true;
    document.addEventListener("visibilitychange", onVisibilityChange);
    acquire();
  }

  function stop() {
    active = false;
    document.removeEventListener("visibilitychange", onVisibilityChange);
    release();
  }

  onUnmounted(stop);

  return { start, stop, isActive: sentinel };
}
