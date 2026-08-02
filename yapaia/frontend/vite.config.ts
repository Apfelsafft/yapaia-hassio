import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Set YAPAIA_HA_INGRESS=1 at build time when bundling for the Home Assistant
// add-on. The relative base ("./") is required because HA mounts the add-on
// frame under /api/hassio_ingress/<token>/ — absolute /assets/* paths would
// hit HA core, not the add-on nginx.
const isIngress = process.env.YAPAIA_HA_INGRESS === "1";

export default defineConfig({
  base: isIngress ? "./" : "/",
  plugins: [vue()],
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    watch: { usePolling: true },
  },
});
