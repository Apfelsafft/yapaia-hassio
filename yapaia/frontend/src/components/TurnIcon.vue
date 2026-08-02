<script setup lang="ts">
// GraphHopper sign codes:
// -98 U-turn unknown  -8 U-turn left  -7 keep left  -3 sharp left
//  -2 left  -1 slight left  0 straight  1 slight right  2 right
//   3 sharp right  4 finish  5 waypoint  6 roundabout  7 keep right  8 U-turn right
defineProps<{ sign: number; exitNumber?: number; size?: number }>();
</script>

<template>
  <svg
    :width="size ?? 80"
    :height="size ?? 80"
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
  >

    <!-- ── STRAIGHT ─────────────────────────────────────────────────────── -->
    <template v-if="sign === 0">
      <path fill="currentColor" stroke="none"
        d="M27,58 L27,26 L20,26 L32,6 L44,26 L37,26 L37,58 Z"/>
    </template>

    <!-- ── SLIGHT RIGHT ────────────────────────────────────────────────── -->
    <template v-else-if="sign === 1">
      <path stroke-width="9" fill="none"
        d="M30,58 C30,42 34,24 46,12"/>
      <polygon fill="currentColor" stroke="none"
        points="36,6 54,16 42,26"/>
    </template>

    <!-- ── TURN RIGHT ──────────────────────────────────────────────────── -->
    <template v-else-if="sign === 2">
      <!-- 90° right: enter from bottom, exit to right
           Turn center (40,30), r_outer=16, r_inner=6 -->
      <path fill="currentColor" stroke="none"
        d="M24,58 L24,30 A16,16 0 0,1 40,14 L50,14 L50,6 L58,20 L50,34 L50,26 L40,26 A6,6 0 0,0 34,30 L34,58 Z"/>
    </template>

    <!-- ── SHARP RIGHT ─────────────────────────────────────────────────── -->
    <template v-else-if="sign === 3">
      <!-- Goes up, tight right hook, exits going lower-right -->
      <path stroke-width="9" fill="none"
        d="M26,58 L26,32 Q26,14 40,14 Q50,14 50,24 L50,36"/>
      <polygon fill="currentColor" stroke="none"
        points="42,28 58,28 51,44"/>
    </template>

    <!-- ── KEEP RIGHT (fork) ───────────────────────────────────────────── -->
    <template v-else-if="sign === 7">
      <line x1="32" y1="58" x2="32" y2="40" stroke-width="9"/>
      <!-- right fork (main) -->
      <path stroke-width="9" fill="none" d="M32,40 L48,16"/>
      <polygon fill="currentColor" stroke="none"
        points="40,8 58,18 46,30"/>
      <!-- left fork (secondary, dimmed) -->
      <path stroke-width="7" fill="none" stroke-opacity="0.28"
        d="M32,40 L18,20"/>
    </template>

    <!-- ── SLIGHT LEFT ─────────────────────────────────────────────────── -->
    <template v-else-if="sign === -1">
      <path stroke-width="9" fill="none"
        d="M34,58 C34,42 30,24 18,12"/>
      <polygon fill="currentColor" stroke="none"
        points="28,6 10,16 22,26"/>
    </template>

    <!-- ── TURN LEFT ───────────────────────────────────────────────────── -->
    <template v-else-if="sign === -2">
      <!-- Mirror of right: Turn center (24,30), r_outer=16, r_inner=6 -->
      <path fill="currentColor" stroke="none"
        d="M40,58 L40,30 A16,16 0 0,0 24,14 L14,14 L14,6 L6,20 L14,34 L14,26 L24,26 A6,6 0 0,1 30,30 L30,58 Z"/>
    </template>

    <!-- ── SHARP LEFT ──────────────────────────────────────────────────── -->
    <template v-else-if="sign === -3">
      <path stroke-width="9" fill="none"
        d="M38,58 L38,32 Q38,14 24,14 Q14,14 14,24 L14,36"/>
      <polygon fill="currentColor" stroke="none"
        points="22,28 6,28 13,44"/>
    </template>

    <!-- ── KEEP LEFT (fork) ────────────────────────────────────────────── -->
    <template v-else-if="sign === -7">
      <line x1="32" y1="58" x2="32" y2="40" stroke-width="9"/>
      <!-- left fork (main) -->
      <path stroke-width="9" fill="none" d="M32,40 L16,16"/>
      <polygon fill="currentColor" stroke="none"
        points="24,8 6,18 18,30"/>
      <!-- right fork (secondary, dimmed) -->
      <path stroke-width="7" fill="none" stroke-opacity="0.28"
        d="M32,40 L46,20"/>
    </template>

    <!-- ── U-TURN LEFT ─────────────────────────────────────────────────── -->
    <template v-else-if="sign === -8 || sign === -98">
      <!-- Enter bottom-right, arc up and left, exit bottom-left -->
      <path stroke-width="9" fill="none"
        d="M42,58 L42,32 Q42,10 32,10 Q20,10 20,22 L20,48"/>
      <polygon fill="currentColor" stroke="none"
        points="10,40 20,58 30,40"/>
    </template>

    <!-- ── U-TURN RIGHT ────────────────────────────────────────────────── -->
    <template v-else-if="sign === 8">
      <path stroke-width="9" fill="none"
        d="M22,58 L22,32 Q22,10 32,10 Q44,10 44,22 L44,48"/>
      <polygon fill="currentColor" stroke="none"
        points="34,40 44,58 54,40"/>
    </template>

    <!-- ── ROUNDABOUT ──────────────────────────────────────────────────── -->
    <template v-else-if="sign === 6">
      <!-- Circle -->
      <circle cx="32" cy="26" r="14" stroke-width="6"/>
      <!-- Entry from bottom -->
      <line x1="32" y1="58" x2="32" y2="40" stroke-width="9"/>

      <!-- Exit RIGHT (default / exit 3) -->
      <template v-if="!exitNumber || exitNumber === 3">
        <line x1="46" y1="26" x2="56" y2="26" stroke-width="7"/>
        <polygon fill="currentColor" stroke="none"
          points="50,18 58,26 50,34"/>
      </template>

      <!-- Exit STRAIGHT (exit 2) -->
      <template v-else-if="exitNumber === 2">
        <line x1="32" y1="12" x2="32" y2="4" stroke-width="7"/>
        <polygon fill="currentColor" stroke="none"
          points="24,10 32,2 40,10"/>
      </template>

      <!-- Exit LEFT (exit 1) -->
      <template v-else-if="exitNumber === 1">
        <line x1="18" y1="26" x2="8" y2="26" stroke-width="7"/>
        <polygon fill="currentColor" stroke="none"
          points="14,18 6,26 14,34"/>
      </template>

      <!-- Exit BACK — almost all the way around (exit 4+) -->
      <template v-else>
        <!-- Entry right side, sweeps around, exits left side going down -->
        <line x1="36" y1="58" x2="36" y2="42" stroke-width="7"/>
        <path d="M36,40 A14,14 0 1,0 28,40" stroke-width="7" fill="none"/>
        <line x1="28" y1="40" x2="28" y2="58" stroke-width="7"/>
        <polygon fill="currentColor" stroke="none"
          points="20,50 28,62 36,50"/>
      </template>
    </template>

    <!-- ── FINISH ──────────────────────────────────────────────────────── -->
    <template v-else-if="sign === 4">
      <!-- Flag pole -->
      <line x1="18" y1="6" x2="18" y2="58" stroke-width="5"/>
      <!-- Flag body (two triangles = checkered) -->
      <path fill="currentColor" stroke="none"
        d="M18,6 L46,13 L18,20 Z"/>
      <!-- Checkered pattern on flag -->
      <rect x="18" y="6"  width="9"  height="4.7" fill="currentColor" stroke="none" opacity="0.55"/>
      <rect x="27" y="10.7" width="9"  height="4.6" fill="currentColor" stroke="none" opacity="0.55"/>
      <rect x="36" y="6"  width="10" height="4.7" fill="currentColor" stroke="none" opacity="0.55"/>
    </template>

    <!-- ── WAYPOINT ─────────────────────────────────────────────────────── -->
    <template v-else-if="sign === 5">
      <!-- Location pin (teardrop) -->
      <path fill="currentColor" stroke="none"
        d="M32,4 A16,16 0 0,1 48,20 Q48,32 32,58 Q16,32 16,20 A16,16 0 0,1 32,4 Z"/>
      <!-- Inner dot (hole) -->
      <circle cx="32" cy="20" r="7" fill="var(--bg-overlay, #1e3a8a)" stroke="none"/>
    </template>

    <!-- ── FALLBACK: straight arrow ─────────────────────────────────────── -->
    <template v-else>
      <path fill="currentColor" stroke="none"
        d="M27,58 L27,26 L20,26 L32,6 L44,26 L37,26 L37,58 Z"/>
    </template>

  </svg>
</template>
