import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BASE_PATH = process.env.VITE_BASE_PATH || "/dataset-curation/auto-labeler-labeler/";

export default defineConfig({
  base: BASE_PATH.endsWith("/") ? BASE_PATH : `${BASE_PATH}/`,
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
