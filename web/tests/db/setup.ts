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