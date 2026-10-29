import { describe, expect, it, vi } from "vitest";

// lib/auth builds the Drizzle adapter over db(), which needs a DATABASE_URL to
// construct the neon client (parseEnv throws without it). The connection is
// never opened by these tests; a non-empty placeholder satisfies the validator.
vi.stubEnv("DATABASE_URL", "postgresql://test@localhost:5432/test");

describe("resolveAuthSecret (review item 5)", () => {
  it("returns AUTH_SECRET when set", async () => {
    vi.stubEnv("AUTH_SECRET", "test-secret");
    const { resolveAuthSecret } = await import("@/lib/auth");
    expect(resolveAuthSecret()).toBe("test-secret");
  });

  it("falls back to a dev-only value outside production", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("AUTH_SECRET", "");
    const { resolveAuthSecret } = await import("@/lib/auth");
    const fallback = resolveAuthSecret();
    expect(fallback.length).toBeGreaterThan(0);
    expect(fallback).not.toBe("test-secret");
  });

  it("throws in production without AUTH_SECRET", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("AUTH_SECRET", "");
    const { resolveAuthSecret } = await import("@/lib/auth");
    expect(() => resolveAuthSecret()).toThrow(/AUTH_SECRET/);
  });
});

describe("assertMailConfig (round 2 item 4)", () => {
  it("is a no-op outside production (print mode can deliver)", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    const { assertMailConfig } = await import("@/lib/mail");
    expect(() => assertMailConfig()).not.toThrow();
  });

  it("throws in production when RESEND_API_KEY or EMAIL_FROM is missing", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    const { assertMailConfig } = await import("@/lib/mail");
    expect(() => assertMailConfig()).toThrow(/email is not configured/);
  });

  it("passes in production when both are set", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "re_prod_key");
    vi.stubEnv("EMAIL_FROM", "no-reply@example.com");
    const { assertMailConfig } = await import("@/lib/mail");
    expect(() => assertMailConfig()).not.toThrow();
  });
});