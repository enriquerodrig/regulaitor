import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// No vite plugins: vitest 3 bundles a rolldown-based vite whose Plugin type
// conflicts with @vitejs/plugin-react's rollup-based one. We resolve the "@"
// alias directly and let esbuild transform JSX (automatic runtime).
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
