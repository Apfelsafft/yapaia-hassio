<script setup lang="ts">
import { useToastsStore } from "../stores/toasts";

const toasts = useToastsStore();
</script>

<template>
  <Teleport to="body">
    <div class="toast-stack">
      <transition-group name="toast">
        <div
          v-for="t in toasts.items"
          :key="t.id"
          class="toast"
          :class="t.kind"
          @click="toasts.dismiss(t.id)"
        >
          <span class="toast-icon">
            {{ t.kind === "success" ? "✓" : t.kind === "error" ? "⚠" : "ℹ" }}
          </span>
          <span class="toast-msg">{{ t.message }}</span>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  display: flex;
  flex-direction: column-reverse;
  gap: 8px;
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #1f2937;
  color: white;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  cursor: pointer;
  min-width: 180px;
  max-width: 360px;
}

.toast.success { background: #15803d; }
.toast.error   { background: #b91c1c; }

.toast-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.toast-msg { flex: 1; line-height: 1.4; }

.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-enter-to,
.toast-leave-from { opacity: 1; transform: translateY(0); }
.toast-leave-to   { opacity: 0; transform: translateY(8px); }
.toast-enter-active,
.toast-leave-active { transition: opacity 0.2s, transform 0.2s; }
</style>
