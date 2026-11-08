/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev (npm run dev) the page runs on :5173 and forwards API + image calls to the
// Python server on :8766. In production FastAPI serves the built files itself.
const backend = { target: "http://127.0.0.1:8766", changeOrigin: true };

export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": backend, "/media": backend } },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"], globals: true },
});
