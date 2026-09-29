import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "./",
  build: {
    // NOTE: relative to frontend/web — must reach the repo-root extension/
    // folder that manifest.json actually loads (NOT frontend/extension/).
    outDir: "../../extension/ui/dist",
    emptyOutDir: true,
  },
});
