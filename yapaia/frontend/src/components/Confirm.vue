<script setup lang="ts">
import { useConfirmStore } from "../stores/confirm";

const cf = useConfirmStore();
</script>

<template>
  <Teleport to="body">
    <transition name="cf">
      <div v-if="cf.active" class="cf-overlay" @click.self="cf.answer(false)">
        <div class="cf-card">
          <h3 class="cf-title">{{ cf.active.title }}</h3>
          <p v-if="cf.active.message" class="cf-msg">{{ cf.active.message }}</p>
          <div class="cf-actions">
            <button class="cf-cancel" @click="cf.answer(false)">
              {{ cf.active.cancelText ?? "Abbrechen" }}
            </button>
            <button class="cf-ok" :class="{ danger: cf.active.danger }" @click="cf.answer(true)">
              {{ cf.active.confirmText ?? "Bestätigen" }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.cf-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 150;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.cf-card {
  background: white;
  border-radius: 14px;
  padding: 20px 22px 16px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.cf-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}

.cf-msg {
  margin: 0 0 16px;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
}

.cf-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.cf-cancel {
  padding: 8px 14px;
  background: white;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.cf-cancel:hover { background: #f9fafb; }

.cf-ok {
  padding: 8px 14px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.cf-ok:hover { background: #2563eb; }

.cf-ok.danger { background: #dc2626; }
.cf-ok.danger:hover { background: #b91c1c; }

.cf-enter-from, .cf-leave-to { opacity: 0; }
.cf-enter-to, .cf-leave-from { opacity: 1; }
.cf-enter-active, .cf-leave-active { transition: opacity 0.15s; }
.cf-enter-from .cf-card, .cf-leave-to .cf-card { transform: scale(0.96); }
.cf-enter-to .cf-card, .cf-leave-from .cf-card { transform: scale(1); }
</style>
