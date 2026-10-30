import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/admin/settings/route";

// The route is tested offline: auth (getSession) and the database chain are
// mocked, invite-route pattern. The real assertSameOrigin runs, so the forged-
// Origin test is meaningful; AUTH_URL is unset in tests, so the trusted origin
// is the localhost default. The end-to-end behaviour against a real database
// lives in tests/db/auth.test.ts.
const authMock = vi.hoisted(() => ({
  api: {
    getSession: vi.fn<() => Promise<unknown>>(async () => null),
  },
}));

const dbState = vi.hoisted(() => ({
  rows: [] as unknown[],
  setValues: null as { value?: unknown; updatedAt?: unknown; updatedBy?: unknown } | null,
  updateReturned: [] as unknown[],
}));

vi.mock("@/lib/auth", () => ({ getAuth: () => authMock }));

vi.mock("@/lib/db", () => ({
  db: () => ({
    select: () => ({
      from: () => ({
        leftJoin: () => ({
          orderBy: async () => dbState.rows,
        }),
      }),
    }),
    update: () => ({
      set: (values: unknown) => {
        dbState.setValues = values as { value?: unknown; updatedAt?: unknown; updatedBy?: unknown };
        return {
          where: () => ({
            returning: async () => dbState.updateReturned,
          }),
        };
      },
    }),
  }),
}));

const SAME_ORIGIN = "http://localhost:3000";

function settingsRequest(
  method: "GET" | "POST",
  options: { body?: unknown; rawBody?: string; origin?: string | null } = {},
): Request {
  const headers: Record<string, string> = { cookie: "better-auth.session_token=x" };
  const origin = options.origin === undefined ? (method === "POST" ? SAME_ORIGIN : undefined) : options.origin;
  if (origin !== null && origin !== undefined) headers.origin = origin;
  const init: RequestInit = { method, headers };
  if (options.rawBody !== undefined) {
    headers["content-type"] = "application/json";
    init.body = options.rawBody;
  } else if (options.body !== undefined) {
    headers["content-type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  return new Request(`${SAME_ORIGIN}/api/admin/settings`, init);
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
  dbState.rows = [];
  dbState.setValues = null;
  dbState.updateReturned = [];
});

describe("GET /api/admin/settings", () => {
  it("lists every row with the updater's email", async () => {
    sessionWith("admin");
    dbState.rows = [
      {
        key: "ask_daily_limit_per_user",
        value: 5,
        description: "How many Ask questions each person can send per day",
        updatedAt: new Date("2026-10-30T08:00:00.000Z"),
        updatedBy: null,
        updatedByEmail: null,
      },
      {
        key: "analysis_refresh_after_days",
        value: 30,
        description: "Refresh a saved analysis older than this",
        updatedAt: new Date("2026-10-30T08:00:00.000Z"),
        updatedBy: "u-1",
        updatedByEmail: "u@example.com",
      },
    ];
    const response = await GET(settingsRequest("GET"));
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      settings: [
        {
          key: "ask_daily_limit_per_user",
          value: 5,
          description: "How many Ask questions each person can send per day",
          updatedAt: "2026-10-30T08:00:00.000Z",
          updatedBy: null,
          updatedByEmail: null,
        },
        {
          key: "analysis_refresh_after_days",
          value: 30,
          description: "Refresh a saved analysis older than this",
          updatedAt: "2026-10-30T08:00:00.000Z",
          updatedBy: "u-1",
          updatedByEmail: "u@example.com",
        },
      ],
    });
  });

  it("refuses a missing session with 401", async () => {
    sessionWith(null);
    const response = await GET(settingsRequest("GET"));
    expect(response.status).toBe(401);
  });

  it("refuses a signed-in non-admin with 403", async () => {
    sessionWith("user");
    const response = await GET(settingsRequest("GET"));
    expect(response.status).toBe(403);
  });
});

describe("POST /api/admin/settings", () => {
  it("an admin edits one row: writes the parsed value and the admin's id, returns the saved row", async () => {
    sessionWith("admin");
    dbState.updateReturned = [
      {
        key: "ask_daily_limit_per_user",
        value: 7,
        description: "How many Ask questions each person can send per day",
        updatedAt: new Date("2026-10-30T08:00:00.000Z"),
        updatedBy: "u-1",
      },
    ];
    const response = await POST(
      settingsRequest("POST", { body: { key: "ask_daily_limit_per_user", value: 7 } }),
    );
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      settings: {
        key: "ask_daily_limit_per_user",
        value: 7,
        description: "How many Ask questions each person can send per day",
        updatedAt: "2026-10-30T08:00:00.000Z",
        updatedBy: "u-1",
        updatedByEmail: "u@example.com",
      },
    });
    expect(dbState.setValues).toMatchObject({ value: 7, updatedBy: "u-1" });
    expect(dbState.setValues?.updatedAt).toBeInstanceOf(Date);
  });

  it("refuses a bad value with 400 and writes nothing", async () => {
    sessionWith("admin");
    const response = await POST(
      settingsRequest("POST", { body: { key: "ask_daily_limit_per_user", value: -1 } }),
    );
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "value must be at least 0" });
    expect(dbState.setValues).toBeNull();
  });

  it("refuses a value that is not a JSON number with 400 and writes nothing", async () => {
    sessionWith("admin");
    const response = await POST(
      settingsRequest("POST", { body: { key: "ask_daily_limit_per_user", value: "5" } }),
    );
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "value must be a number" });
    expect(dbState.setValues).toBeNull();
  });

  it("refuses bad JSON with 400", async () => {
    sessionWith("admin");
    const response = await POST(settingsRequest("POST", { rawBody: "{ not json" }));
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "invalid json" });
    expect(dbState.setValues).toBeNull();
  });

  it("refuses an unknown key with 400 and writes nothing", async () => {
    sessionWith("admin");
    const response = await POST(settingsRequest("POST", { body: { key: "not_a_real_key", value: 1 } }));
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "unknown settings key" });
    expect(dbState.setValues).toBeNull();
  });

  it("answers 404 for a known key with no row, creating nothing", async () => {
    sessionWith("admin");
    const response = await POST(
      settingsRequest("POST", { body: { key: "analysis_daily_limit_platform", value: 10 } }),
    );
    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toEqual({ error: "settings row not found" });
    expect(dbState.setValues).toMatchObject({ value: 10, updatedBy: "u-1" });
  });

  it("refuses a missing session with 401 and a signed-in non-admin with 403", async () => {
    sessionWith(null);
    expect((await POST(settingsRequest("POST", { body: { key: "ask_daily_limit_per_user", value: 5 } }))).status).toBe(401);
    sessionWith("user");
    expect((await POST(settingsRequest("POST", { body: { key: "ask_daily_limit_per_user", value: 5 } }))).status).toBe(403);
    expect(dbState.setValues).toBeNull();
  });

  it("refuses a forged-Origin POST even with an admin session", async () => {
    sessionWith("admin");
    const response = await POST(
      settingsRequest("POST", {
        body: { key: "ask_daily_limit_per_user", value: 5 },
        origin: "https://evil.example",
      }),
    );
    expect(response.status).toBe(403);
    expect(dbState.setValues).toBeNull();
  });
});