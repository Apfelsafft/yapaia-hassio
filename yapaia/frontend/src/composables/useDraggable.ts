import { reactive, ref, computed, onUnmounted } from "vue";

const STORAGE_KEY = "navi_ui_positions";

function loadStored(): Record<string, { x: number; y: number }> {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch { return {}; }
}

// Shared reactive store — all useDraggable instances read/write the same object.
// Deleting a key makes the computed style return {}, snapping the element back.
const globalPos = reactive<Record<string, { x: number; y: number } | null>>(loadStored());

function persistAll() {
  const out: Record<string, { x: number; y: number }> = {};
  for (const [k, v] of Object.entries(globalPos)) { if (v) out[k] = v; }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(out));
}

export function resetAllDraggablePositions() {
  for (const k of Object.keys(globalPos)) delete globalPos[k];
  localStorage.removeItem(STORAGE_KEY);
}

function clamp(v: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, v)); }

export function useDraggable(key: string) {
  const active = ref(false);
  let timer: ReturnType<typeof setTimeout> | null = null;
  let startPtr = { x: 0, y: 0 };
  let startEl = { x: 0, y: 0 };
  let captEl: HTMLElement | null = null;
  let captId = 0;
  let ateClick = false;

  // When a custom position is stored, override element positioning to fixed.
  // right/bottom/transform are reset so default CSS anchoring doesn't fight the override.
  const style = computed(() => {
    const p = globalPos[key];
    if (!p) return {};
    return {
      position: "fixed" as const,
      left: `${p.x}px`,
      top: `${p.y}px`,
      right: "auto",
      bottom: "auto",
      transform: "none",
    };
  });

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0 && e.pointerType !== "touch") return;
    startPtr = { x: e.clientX, y: e.clientY };
    captEl = e.currentTarget as HTMLElement;
    const r = captEl.getBoundingClientRect();
    startEl = { x: r.left, y: r.top };
    captId = e.pointerId;
    timer = setTimeout(() => {
      active.value = true;
      captEl?.setPointerCapture(captId);
    }, 500);
  }

  function onPointerMove(e: PointerEvent) {
    if (!active.value) {
      if (Math.hypot(e.clientX - startPtr.x, e.clientY - startPtr.y) > 8) clearTimer();
      return;
    }
    e.preventDefault();
    globalPos[key] = {
      x: clamp(startEl.x + (e.clientX - startPtr.x), 4, window.innerWidth - 48),
      y: clamp(startEl.y + (e.clientY - startPtr.y), 4, window.innerHeight - 48),
    };
  }

  function onPointerUp() {
    clearTimer();
    if (active.value) {
      active.value = false;
      ateClick = true;
      persistAll();
    }
  }

  function onPointerCancel() {
    clearTimer();
    active.value = false;
  }

  // Place this on the draggable element via @click.capture.
  // If a drag just ended, stopImmediatePropagation prevents inner click handlers from firing.
  function guardClick(e: MouseEvent) {
    if (ateClick) {
      ateClick = false;
      e.stopImmediatePropagation();
      e.preventDefault();
    }
  }

  function clearTimer() {
    if (timer) { clearTimeout(timer); timer = null; }
  }

  function reset() {
    delete globalPos[key];
    persistAll();
  }

  onUnmounted(clearTimer);

  return { style, active, onPointerDown, onPointerMove, onPointerUp, onPointerCancel, guardClick, reset };
}
