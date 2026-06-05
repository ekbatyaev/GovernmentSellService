import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/goszakupki/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/goszakupki": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },
});