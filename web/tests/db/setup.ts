// The db tests run only against the throwaway branch the harness created.
// Without the marker, a local run (even with a stale DATABASE_URL pointing at
// `dev`) could touch a real branch — refuse instead.
if (!process.env.NEON_TEST_BRANCH_ID) {
  throw new Error(
    "NEON_TEST_BRANCH_ID is not set: the database tests only run under `npm run test:db` " +
      "(web/scripts/neon-branch.mjs) against the branch it creates. A plain `npm test` " +
      "never runs them.",
  );
}

// Vitest sets `process.env.TEST = "true"` in every worker (the pool env the
// threads/forks worker starts with), and Better Auth's `isTest()` is
// `NODE_ENV === "test" || toBoolean(env.TEST)`
// (@better-auth/core/dist/env/env-impl.mjs). `createAuthContext` then sets
// `skipOriginCheck: isTest() ? true : false` (better-auth/dist/context/
// create-context.mjs), which disables exactly the origin and CSRF checks the
// forged-Origin test exists to exercise. The harness's `NODE_ENV=development`
// (web/scripts/neon-branch.mjs) fixes only the first half of `isTest()`; delete
// the vitest half here, before anything builds the auth instance, so the checks
// run for real. Production never sets TEST, so this is a test-only concern.
delete process.env.TEST;