import { beforeEach, describe, expect, it, vi } from "vitest";

// The auth instance is built lazily (next build evaluates modules without env),
// so the fail-fast checks run on the first buildAuth()/getAuth() call. Each
// `it` re-evaluates lib/auth from a clean module registry and stubs the env
// the test needs. lib/auth constructs the adapter over db(), which needs a
// non-empty DATABASE_URL to build the client (parseEnv), but no connection is
// ever opened.
beforeEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
  vi.stubEnv("DATABASE_URL", "postgresql://test@localhost:5432/test");
});

describe("production fails fast without the config (round 2 item 4)", () => {
  it("throws when AUTH_SECRET is missing", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_SECRET", "");
    vi.stubEnv("RESEND_API_KEY", "re_prod_key");
    vi.stubEnv("EMAIL_FROM", "no-reply@example.com");
    const { getAuth } = await import("@/lib/auth");
    expect(() => getAuth()).toThrow(/AUTH_SECRET/);
  });

  it("throws when the mail config is missing", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_SECRET", "a-real-production-secret");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    const { getAuth } = await import("@/lib/auth");
    expect(() => getAuth()).toThrow(/email is not configured/);
  });

  it("starts outside production without either", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("AUTH_SECRET", "");
    const { getAuth } = await import("@/lib/auth");
    expect(getAuth()).toBeDefined();
    // The config the app relies on (ADR-0028): no public sign-up.
    expect(getAuth().options.emailAndPassword?.disableSignUp).toBe(true);
  });
});