import { defineStore } from "pinia";
import { ref } from "vue";

export type CameraQuality = "low" | "medium" | "high" | "hd";

export interface QualityOption {
  key: CameraQuality;
  label: string;
  width: number;      // capture width in px
  jpegQuality: number; // 0–1
  fps: number;
}

export const QUALITY_OPTIONS: QualityOption[] = [
  { key: "low",    label: "Niedrig", width: 320,  jpegQuality: 0.5,  fps: 5  },
  { key: "medium", label: "Mittel",  width: 640,  jpegQuality: 0.7,  fps: 10 },
  { key: "high",   label: "Hoch",    width: 960,  jpegQuality: 0.85, fps: 15 },
  { key: "hd",     label: "HD",      width: 1280, jpegQuality: 0.92, fps: 15 },
];

export interface CameraStreamConfig {
  enabled: boolean;
  quality: CameraQuality;
}

const STORAGE_KEY = "navi_camera_streams";

export const useCameraStore = defineStore("camera", () => {
  /** Camera devices, populated after first getUserMedia permission grant */
  const devices = ref<MediaDeviceInfo[]>([]);

  /** Per-camera stream config, keyed by camera index (as number) */
  const configs = ref<Record<number, CameraStreamConfig>>({});

  function _persist() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(configs.value)); } catch {}
  }

  function _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) configs.value = JSON.parse(raw);
    } catch {}
  }

  function getConfig(idx: number): CameraStreamConfig {
    return configs.value[idx] ?? { enabled: false, quality: "medium" };
  }

  function setConfig(idx: number, patch: Partial<CameraStreamConfig>) {
    configs.value = { ...configs.value, [idx]: { ...getConfig(idx), ...patch } };
    _persist();
  }

  _load();

  return { devices, configs, getConfig, setConfig };
});
