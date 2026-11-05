import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, ".") } },
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", ".next"],
    coverage: {
      provider: "v8",
      include: ["lib/**/*.ts", "components/**/*.tsx"],
      // Server-only modules and async Server Components are exercised by Playwright end-to-end.
      exclude: ["lib/api-server.ts", "components/listing-card.tsx", "components/search-filters.tsx",
                "components/demo-banner.tsx", "**/*.test.*"],
      thresholds: { lines: 85, branches: 85, functions: 85, statements: 85 },
      reporter: ["text", "html", "json-summary"],
    },
  },
});
