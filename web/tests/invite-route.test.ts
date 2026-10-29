import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/admin/invite/route";

// The route is tested offline: auth (sessions + requestPasswordReset), the
// database chain and the mail delivery are all mocked. The existing-address
// behaviour needs a real database and lives in tests/db/ (review item 7).
const authMock = vi.hoisted(() => ({
  api: {
    requestPasswordReset: vi.fn<() => Promise<{ status: boolean }>>(async () => ({ status: true })),
    getSession: vi.fn<() => Promise<unknown>>(async () => null),
  },
}));

const dbState = vi.hoisted(() => ({
  existing: [] as { id: string }[],
  insertedIds: [] as string[],
  voidedCount: 0,
}));

vi.mock("@/lib/auth", () => ({ getAuth: () => authMock }));

vi.mock("@/lib/db", () => ({
  db: () => ({
    select: () => ({ from: () => ({ where: () => ({ limit: async () => dbState.existing }) }) }),
    insert: () => ({
      values: () => ({
        returning: async () => {
          dbState.insertedIds.push("inserted-user-id");
          return [{ id: "inserted-user-id" }];
        },
      }),
    }),
    delete: () => ({
      where: async () => {
        dbState.voidedCount += 1;
        return { rowCount: 0 };
      },
    }),
  }),
}));

// Keep the real assertMailConfig (the 500 branch runs against it, round 2 item
// 4); mock only delivery so "no mail sent" is observable.
vi.mock("@/lib/mail", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/mail")>();
  return { ...actual, sendAccountEmail: vi.fn<() => Promise<void>>(async () => {}) };
});

import { sendAccountEmail } from "@/lib/mail";

const SAME_ORIGIN = "http://localhost:3000";

function inviteRequest(body: unknown, origin: string | null = SAME_ORIGIN): Request {
  const headers: Record<string, string> = { "content-type": "application/json", cookie: "better-auth.session_token=x" };
  if (origin !== null) headers.origin = origin;
  return new Request("http://localhost:3000/api/admin/invite", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

function sessionWith(role: string | null) {
  if (role === null) {
    authMock.api.getSession.mockResolvedValueOnce(null);
    return;
  }
  authMock.api.getSession.mockResolvedValueOnce({
    session: { id: "s-1" },
    user: { id: "u-1", email: "u@example.com", role },
  } as never);
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
  dbState.existing = [];
  dbState.insertedIds = [];
  dbState.voidedCount = 0;
});

describe("POST /api/admin/invite", () => {
  it("invites a new address: creates a user row and calls requestPasswordReset", async () => {
    sessionWith("admin");
    const response = await POST(inviteRequest({ email: "new@example.com", name: "New Person" }));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, message: "Invite sent" });
    expect(dbState.insertedIds).toEqual(["inserted-user-id"]);
    expect(authMock.api.requestPasswordReset).toHaveBeenCalledWith({
      body: { email: "new@example.com", redirectTo: "/reset-password" },
    });
  });

  it("invites an existing address without a new row (review item 7)", async () => {
    sessionWith("admin");
    dbState.existing = [{ id: "existing-id" }];
    const response = await POST(inviteRequest({ email: "existing@example.com" }));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true, message: "Invite sent" });
    expect(dbState.insertedIds).toEqual([]);
    expect(dbState.voidedCount).toBe(1);
    expect(authMock.api.requestPasswordReset).toHaveBeenCalled();
  });

  it("refuses an unauthenticated request with 401", async () => {
    sessionWith(null);
    const response = await POST(inviteRequest({ email: "new@example.com" }));
    expect(response.status).toBe(401);
    expect(authMock.api.requestPasswordReset).not.toHaveBeenCalled();
  });

  it("refuses a signed-in non-admin with 403", async () => {
    sessionWith("user");
    const response = await POST(inviteRequest({ email: "new@example.com" }));
    expect(response.status).toBe(403);
    expect(authMock.api.requestPasswordReset).not.toHaveBeenCalled();
  });

  it("refuses a cross-origin POST even with an admin session (review item 3)", async () => {
    sessionWith("admin");
    const response = await POST(inviteRequest({ email: "new@example.com" }, "https://evil.example"));
    expect(response.status).toBe(403);
    expect(authMock.api.requestPasswordReset).not.toHaveBeenCalled();
    expect(dbState.insertedIds).toEqual([]);
  });

  it("rejects a malformed email with 400 and sends nothing", async () => {
    sessionWith("admin");
    const response = await POST(inviteRequest({ email: "not-an-email" }));
    expect(response.status).toBe(400);
    expect(authMock.api.requestPasswordReset).not.toHaveBeenCalled();
    expect(dbState.insertedIds).toEqual([]);
    expect(sendAccountEmail).not.toHaveBeenCalled();
  });

  it("answers 500 before creating any row when mail is not configured (round 2 item 4)", async () => {
    sessionWith("admin");
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    const response = await POST(inviteRequest({ email: "new@example.com" }));
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({ error: "email is not configured" });
    expect(dbState.insertedIds).toEqual([]);
    expect(authMock.api.requestPasswordReset).not.toHaveBeenCalled();
    expect(sendAccountEmail).not.toHaveBeenCalled();
  });
});