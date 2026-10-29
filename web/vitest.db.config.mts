import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// The database tests. Only the harness (web/scripts/neon-branch.mjs, `npm run
// test:db`) runs this config: it points DATABASE_URL at the throwaway branch it
// created and sets NEON_TEST_BRANCH_ID, without which setup.ts refuses to start.
// A plain `npm test` never loads this file (vitest.config.mts excludes tests/db/**).
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "node",
    include: ["tests/db/**/*.test.ts"],
    setupFiles: ["./tests/db/setup.ts"],
  },
});