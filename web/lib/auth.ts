import { betterAuth, type BetterAuthOptions } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { account, rateLimit, session, users, verification } from "@/db/schema";
import { db } from "@/lib/db";
import { assertMailConfig, sendResetPasswordMail } from "@/lib/mail";

// One shared bucket per IP+path before the host is chosen (D11): the database
// store is per-config, not per-instance, so serverless instances agree on the
// limits even though `advanced.ipAddress` isn't configured yet. Security
// parameters, not product quotas — AGENTS.md rule 6 keeps quotas in `settings`.
const RATE_LIMIT_WINDOW_SIGN_IN = 900; // 15 minutes
const RATE_LIMIT_MAX_SIGN_IN = 10;
const RATE_LIMIT_WINDOW_RESET = 3600; // 1 hour
const RATE_LIMIT_MAX_RESET = 5;

const DEV_AUTH_SECRET = "dev-only-insecure-auth-secret-do-not-use-in-production";

/**
 * AUTH_SECRET resolution. Better Auth accepts `AUTH_SECRET` itself and throws
 * in production when it's missing; this makes the same rule explicit and
 * testable: outside production, a dev-only fallback (never a real value) lets
 * local runs and the Neon harness work without a secret (review item 5).
 */
export function resolveAuthSecret(): string {
  if (process.env.AUTH_SECRET) return process.env.AUTH_SECRET;
  if (process.env.NODE_ENV === "production") {
    throw new Error("AUTH_SECRET is required in production");
  }
  return DEV_AUTH_SECRET;
}

/**
 * Build the Better Auth server instance. Lazy, not module-scope: `next build`
 * evaluates route modules with no environment variables, and db() refuses to
 * construct without DATABASE_URL. First use constructs and caches it; in
 * production the first use fails fast with a clear error when AUTH_SECRET or
 * the mail config is missing — the same check the plan wants at server start,
 * the earliest point a Next.js app can actually run it (round 2 item 4).
 */
export function buildAuth(): ReturnType<typeof betterAuth> {
  if (process.env.NODE_ENV === "production") {
    resolveAuthSecret();
    assertMailConfig();
  }
  const options: BetterAuthOptions = {
    database: drizzleAdapter(db(), {
      provider: "pg",
      // Better Auth's model names map onto our tables. `user` maps onto the
      // existing `users` table; db.md's columns (uuid id, citext email, role)
      // stay exactly as they are (review item 2).
      schema: { user: users, session, account, verification, rateLimit },
    }),
    baseURL: process.env.AUTH_URL ?? "http://localhost:3000",
    secret: resolveAuthSecret(),
    emailAndPassword: {
      enabled: true,
      // Invite-only: no public sign-up (ADR-0028).
      disableSignUp: true,
      // A reset ends every live session: recovering a compromised account also
      // kicks an attacker's session out (round 2 item 5).
      revokeSessionsOnPasswordReset: true,
      // One mechanism, one expiry for both invite and reset links (decision 2):
      // seconds, the unit 1.7.14 expects (round 2 item 2).
      resetPasswordTokenExpiresIn: 60 * 60 * 24,
      sendResetPassword: sendResetPasswordMail,
    },
    user: {
      // No admin plugin (review item 1): the app's only admin concept is
      // `users.role`, read and written through this mapping, and the client can
      // never set it. No ban/impersonation fields exist in the schema.
      additionalFields: {
        role: { type: "string", input: false },
      },
    },
    rateLimit: {
      // 1.7.14 switches the limiter off unless NODE_ENV === "production", so
      // enable explicitly; the default store is per-instance memory, so keep it
      // in the database (review item 4).
      enabled: true,
      storage: "database",
      // Keyed by client IP and path — an object keyed by path, per 1.7.14
      // (round 2 item 3). `/api/admin/invite` is deliberately not behind the
      // library limiter: admin-only plus the role and origin checks is the gate.
      customRules: {
        "/sign-in/email": { window: RATE_LIMIT_WINDOW_SIGN_IN, max: RATE_LIMIT_MAX_SIGN_IN },
        "/request-password-reset": { window: RATE_LIMIT_WINDOW_RESET, max: RATE_LIMIT_MAX_RESET },
      },
    },
    advanced: {
      // generateId: "uuid" makes Better Auth generate its own ids for the auth
      // tables, as UUIDs that fit the uuid columns (review item 2). The
      // columns' database defaults are only a fallback for the rows the app
      // inserts itself (code review round 1 finding 8).
      database: { generateId: "uuid" },
    },
  };
  return betterAuth(options);
}

let cachedAuth: ReturnType<typeof buildAuth> | undefined;

/** The app's single Better Auth instance (ADR-0025: one connection). */
export function getAuth(): ReturnType<typeof buildAuth> {
  cachedAuth ??= buildAuth();
  return cachedAuth;
}