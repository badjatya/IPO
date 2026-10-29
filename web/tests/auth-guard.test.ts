import { describe, expect, it, vi } from "vitest";

const authMock = vi.hoisted(() => ({
  api: { getSession: vi.fn<() => Promise<unknown>>(async () => null) },
}));
vi.mock("@/lib/auth", () => ({ getAuth: () => authMock }));

import { assertSameOrigin, AuthError, getSessionUser, requireAdmin } from "@/lib/auth-guard";

function sessionFor(role: string | null) {
  if (role === null) return null;
  return {
    session: { id: "s-1", expiresAt: new Date().toISOString() },
    user: { id: "u-1", email: "u@example.com", name: null, emailVerified: true, role },
  } as never;
}

describe("getSessionUser / requireAdmin", () => {
  it("returns null with no session", async () => {
    authMock.api.getSession.mockResolvedValueOnce(null);
    await expect(getSessionUser(new Headers())).resolves.toBeNull();
  });

  it("returns the signed-in user with their role", async () => {
    authMock.api.getSession.mockResolvedValueOnce(sessionFor("admin"));
    await expect(getSessionUser(new Headers())).resolves.toMatchObject({ id: "u-1", role: "admin" });
  });

  it("requireAdmin throws 401 without a session", async () => {
    authMock.api.getSession.mockResolvedValueOnce(null);
    await expect(requireAdmin(new Headers())).rejects.toMatchObject({ status: 401 });
  });

  it("requireAdmin throws 403 for a signed-in non-admin (review item 1)", async () => {
    authMock.api.getSession.mockResolvedValueOnce(sessionFor("user"));
    await expect(requireAdmin(new Headers())).rejects.toMatchObject({ status: 403 });
  });

  it("requireAdmin resolves for an admin", async () => {
    authMock.api.getSession.mockResolvedValueOnce(sessionFor("admin"));
    await expect(requireAdmin(new Headers())).resolves.toMatchObject({ id: "u-1", role: "admin" });
  });
});

function requestWith(origin: string | null): Request {
  const headers: Record<string, string> = {};
  if (origin !== null) headers.origin = origin;
  return new Request("http://localhost:3000/api/admin/invite", { method: "POST", headers });
}

describe("assertSameOrigin (review item 3)", () => {

  it("accepts the AUTH_URL origin", () => {
    expect(() => assertSameOrigin(requestWith("http://localhost:3000"))).not.toThrow();
  });

  it("accepts the AUTH_URL origin when set", () => {
    vi.stubEnv("AUTH_URL", "https://app.example.com");
    expect(() => assertSameOrigin(requestWith("https://app.example.com"))).not.toThrow();
  });

  it("refuses a cross-site origin and a missing origin", () => {
    expect(() => assertSameOrigin(requestWith("https://evil.example"))).toThrow(AuthError);
    expect(() => assertSameOrigin(requestWith(null))).toThrow(AuthError);
  });
});