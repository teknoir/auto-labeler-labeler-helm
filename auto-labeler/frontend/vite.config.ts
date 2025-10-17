import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const basePath = (process.env.VITE_BASE_PATH || "/").replace(/\/?$/, "/");

export default defineConfig({
  base: basePath,
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: ['teknoir.cloud'], // allow external host header
    cors: true,
    origin: `https://teknoir.cloud${basePath}`, // fixes HMR websockets behind proxy
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
