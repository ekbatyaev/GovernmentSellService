import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // В dev проксируем роутеры бэка (в Docker фронт и API отдаёт один FastAPI)
    proxy: Object.fromEntries(
      ["/users", "/purchases", "/newsletters", "/services"].map((path) => [
        path,
        { target: "http://localhost:8002", changeOrigin: true },
      ]),
    ),
  },
});