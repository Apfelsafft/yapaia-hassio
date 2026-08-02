<script setup lang="ts">
defineProps<{
  /** Optional explanation shown in the tooltip. */
  label?: string;
  /** Render as inline pill (default) or compact lock icon only. */
  compact?: boolean;
}>();
</script>

<template>
  <span
    class="premium-lock"
    :class="{ compact }"
    :title="label || 'Premium-Feature — Upgrade nötig'"
  >
    <span class="lock-icon">🔒</span>
    <span v-if="!compact" class="lock-text">Premium</span>
  </span>
</template>

<style scoped>
.premium-lock {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: linear-gradient(135deg, #fcd34d 0%, #f59e0b 100%);
  color: #78350f;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  vertical-align: middle;
}

.premium-lock.compact {
  padding: 2px 6px;
  letter-spacing: 0;
}

.lock-icon { font-size: 11px; line-height: 1; }
.lock-text { line-height: 1; }
</style>
