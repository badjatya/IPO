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
    // The Neon suite runs against the real ap-southeast-1 branch, where a
    // Better Auth call takes about 1 s (password hashing plus round trips).
    // The first-admin test also blocks the event loop with spawnSync, and the
    // rate-limit test needs up to ten ~1 s failed sign-ins before the 429.
    // Vitest's default 5 s testTimeout made those tests (and every later one
    // that depended on their cookies) time out. The offline suite's config
    // (vitest.config.mts) keeps the default: it is local and fast.
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
});