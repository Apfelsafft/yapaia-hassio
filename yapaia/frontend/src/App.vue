<script setup lang="ts">
import { watch, onMounted } from "vue";
import { useUserStore } from "./stores/user";
import { useMapStore } from "./stores/map";
import { useFavoritesStore } from "./stores/favorites";
import { usePreferencesStore } from "./stores/preferences";
import { useVehiclesStore } from "./stores/vehicles";
import { useThemeStore } from "./stores/theme";
import { useStationsStore } from "./stores/stations";
import { useAddonsStore } from "./stores/addons";
import { useWakeLock } from "./composables/useWakeLock";
import MapView from "./components/MapView.vue";
import SearchBar from "./components/SearchBar.vue";
import RoutePanel from "./components/RoutePanel.vue";
import SettingsModal from "./components/SettingsModal.vue";
import AuthModal from "./components/AuthModal.vue";
import DrivingOverlay from "./components/DrivingOverlay.vue";
import NavControls from "./components/NavControls.vue";
import Toast from "./components/Toast.vue";
import Confirm from "./components/Confirm.vue";
import CameraView from "./components/CameraView.vue";

const userStore = useUserStore();
const mapStore = useMapStore();
const themeStore = useThemeStore();
themeStore.init();

onMounted(async () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  const authError = params.get("auth_error");
  if (token) {
    await userStore.loginWithToken(token);
    window.history.replaceState({}, "", "/");
  } else if (authError) {
    window.history.replaceState({}, "", "/");
  }
});
const favStore = useFavoritesStore();
const prefStore = usePreferencesStore();
const vehiclesStore = useVehiclesStore();
const stationsStore = useStationsStore();
const addonsStore = useAddonsStore();
const wakeLock = useWakeLock();

watch(
  () => mapStore.isNavigating,
  (navigating) => {
    if (navigating) wakeLock.start();
    else wakeLock.stop();
  },
);

watch(
  () => userStore.isLoggedIn,
  async (loggedIn) => {
    if (loggedIn) {
      await Promise.all([favStore.load(), prefStore.load(), vehiclesStore.load()]);
      mapStore.applyPreferences(prefStore.data);
      // Load installed addons and their settings
      await addonsStore.fetchInstalled();
      if (addonsStore.isInstalled("tankerkoenig")) {
        await addonsStore.fetchSettings("tankerkoenig");
      }
      if (addonsStore.isInstalled("track_recorder")) {
        addonsStore.startTrackPolling();
      }
      // Tankstellen-Sichtbarkeit aus Präferenzen wiederherstellen
      stationsStore.setVisible(prefStore.data.stations_enabled ?? false);
    } else {
      favStore.reset();
      prefStore.reset();
      vehiclesStore.reset();
      stationsStore.clear();
      addonsStore.reset();
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="app">
    <AuthModal v-if="!userStore.isLoggedIn" />
    <template v-else>
      <MapView />
      <DrivingOverlay />
      <NavControls />
      <SearchBar v-if="!mapStore.isNavigating" />
      <RoutePanel />
      <SettingsModal />
      <CameraView v-if="addonsStore.isInstalled('camera')" />
      <div v-if="mapStore.isRerouting" class="reroute-banner">
        🔄 Neue Route wird berechnet…
      </div>
      <div
        v-else-if="mapStore.rerouteError"
        class="reroute-banner error"
        @click="mapStore.rerouteError = null"
        title="Antippen zum Schließen"
      >
        ⚠ Neuberechnung fehlgeschlagen
      </div>
    </template>

    <!-- Global UI primitives — always mounted -->
    <Toast />
    <Confirm />
  </div>
</template>

<style scoped>
.app {
  position: relative;
  width: 100%;
  height: 100%;
}

.reroute-banner {
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: #1d4ed8;
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
  z-index: 30;
  pointer-events: none;
}

.reroute-banner.error {
  background: #b91c1c;
  pointer-events: auto;
  cursor: pointer;
}
</style>
