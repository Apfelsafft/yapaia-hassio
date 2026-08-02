import { createApp } from "vue";
import { createPinia } from "pinia";
import { Protocol } from "pmtiles";
import maplibregl from "maplibre-gl";
import App from "./App.vue";
import "./style.css";
import "maplibre-gl/dist/maplibre-gl.css";

// Register pmtiles:// protocol so MapLibre can load offline vector tiles
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile.bind(protocol));

createApp(App).use(createPinia()).mount("#app");
