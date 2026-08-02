import type { StyleSpecification } from "maplibre-gl";

export interface MapStyleDef {
  id: string;
  name: string;
  description: string;
  previewColor: string;
}

function cartoRaster(
  variant: string,
  paint: Record<string, unknown> = {},
): StyleSpecification {
  const hosts = ["a", "b", "c"];
  return {
    version: 8,
    sources: {
      carto: {
        type: "raster",
        tiles: hosts.map((h) => `https://${h}.basemaps.cartocdn.com/${variant}/{z}/{x}/{y}.png`),
        tileSize: 256,
        attribution:
          "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors © <a href='https://carto.com/attributions'>CARTO</a>",
        maxzoom: 19,
      },
    },
    layers: [{ id: "carto", type: "raster", source: "carto", paint }],
  } as StyleSpecification;
}

export const MAP_STYLES: Record<string, MapStyleDef & { buildStyle: () => StyleSpecification }> = {
  carto_voyager: {
    id: "carto_voyager",
    name: "Voyager",
    description: "Bunt & modern, sehr gut lesbar",
    previewColor: "#f5f0dc",
    buildStyle: () => cartoRaster("rastertiles/voyager"),
  },
  carto_positron: {
    id: "carto_positron",
    name: "Positron",
    description: "Minimalistisch, sehr sauber",
    previewColor: "#f8f8f8",
    buildStyle: () => cartoRaster("light_all"),
  },
  osm_standard: {
    id: "osm_standard",
    name: "OSM Standard",
    description: "Klassischer OpenStreetMap-Stil",
    previewColor: "#aad3df",
    buildStyle: () => ({
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
          maxzoom: 19,
        },
      },
      layers: [{ id: "osm", type: "raster", source: "osm" }],
    } as StyleSpecification),
  },
  open_topo: {
    id: "open_topo",
    name: "Topographisch",
    description: "OpenTopoMap mit Höhenlinien",
    previewColor: "#c8d5a0",
    buildStyle: () => ({
      version: 8,
      sources: {
        topo: {
          type: "raster",
          tiles: ["https://tile.opentopomap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© <a href='https://opentopomap.org'>OpenTopoMap</a> contributors",
          maxzoom: 17,
        },
      },
      layers: [{ id: "topo", type: "raster", source: "topo" }],
    } as StyleSpecification),
  },
  carto_voyager_dusk: {
    id: "carto_voyager_dusk",
    name: "Dämmerung",
    description: "Leicht gedimmt, natürliche Farben — gut bei Regen oder bewölktem Himmel",
    previewColor: "#c8bfa8",
    buildStyle: () =>
      cartoRaster("rastertiles/voyager", {
        "raster-brightness-max": 0.72,
        "raster-saturation": -0.08,
        "raster-contrast": 0.05,
      }),
  },
  carto_voyager_night: {
    id: "carto_voyager_night",
    name: "Nacht",
    description: "Blau getönt & gedimmt — Straßen klar erkennbar, augenschonend",
    previewColor: "#3a4f68",
    buildStyle: () =>
      cartoRaster("rastertiles/voyager", {
        "raster-brightness-min": 0,
        "raster-brightness-max": 0.52,
        "raster-saturation": -0.2,
        "raster-hue-rotate": 190,
        "raster-contrast": 0.12,
      }),
  },
  carto_dark_matter: {
    id: "carto_dark_matter",
    name: "Dark Matter",
    description: "Sehr dunkler Stil — geringer Akkuverbrauch auf OLED-Displays",
    previewColor: "#1a1a2e",
    buildStyle: () => cartoRaster("dark_all"),
  },
};

export const LIGHT_STYLES = ["carto_voyager", "carto_positron", "osm_standard", "open_topo"];
export const DARK_STYLES = ["carto_voyager_night", "carto_voyager_dusk", "carto_dark_matter", "carto_positron"];

export const DEFAULT_LIGHT = "carto_voyager";
export const DEFAULT_DARK = "carto_voyager_night";
