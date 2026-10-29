import { spawnSync } from "node:child_process";
import { afterEach, describe, expect, it, vi } from "vitest";
import { POST as adminInvite } from "@/app/api/admin/invite/route";
import { getAuth } from "@/lib/auth";
import { sql } from "@/lib/db";

// The auth integration suite on a real, disposable Neon branch (run through
// web/scripts/neon-branch.mjs, which supplies DATABASE_URL, NEON_TEST_BRANCH_ID,
// a per-run AUTH_SECRET, AUTH_URL and NODE_ENV=development). Everything goes
// through Better Auth's HTTP handler — sessions, cookies, the origin checks and
// the database rate limiter all run for real — plus the app's own invite route
// and first-admin script. The mail module runs in print mode (development, no
// RESEND_API_KEY): each account email prints to the console and is asserted on.
// Addresses are synthetic example.com only; no real user data and no live sites.

const BASE = "http://localhost:3000";
const AUTH = getAuth();

interface ApiResult {
  status: number;
  json: unknown;
  cookies: string[];
  location: string | null;
}

async function api(
  method: "GET" | "POST",
  path: string,
  options: { body?: unknown; cookie?: string; origin?: string } = {},
): Promise<ApiResult> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["content-type"] = "application/json";
  if (options.cookie) headers.cookie = options.cookie;
  // A browser sends Origin on every POST, and Better Auth's origin check (on
  // for real here — tests/db/setup.ts deletes vitest's TEST env) refuses a
  // cookie-bearing POST without one (403 MISSING_OR_NULL_ORIGIN). Default to
  // the trusted BASE, as a browser of this app would; a test overrides it to
  // forge a cross-site origin.
  const origin = options.origin ?? (method === "POST" ? BASE : undefined);
  if (origin) headers.origin = origin;
  const init: RequestInit = { method, headers };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  const res = await AUTH.handler(new Request(`${BASE}${path}`, init));
  const cookies = res.headers.getSetCookie().map((c) => c.split(";")[0]);
  const json = await res.json().catch(() => null);
  return { status: res.status, json, cookies, location: res.headers.get("location") };
}

/** Capture print-mode mail output; each entry is one console.log call. */
function captureMail() {
  const lines: string[] = [];
  const spy = vi.spyOn(console, "log").mockImplementation((...args: unknown[]) => {
    lines.push(args.map((a) => String(a)).join(" "));
  });
  return {
    lines,
    restore: () => spy.mockRestore(),
    mail: () => lines.filter((l) => l.startsWith("[mail:print]")),
  };
}

async function signInCookie(email: string, password: string): Promise<string> {
  const r = await api("POST", "/api/auth/sign-in/email", { body: { email, password } });
  expect(r.status).toBe(200);
  expect(r.cookies.length).toBeGreaterThan(0);
  return r.cookies.join("; ");
}

async function latestResetToken(userId: string): Promise<string> {
  const rows = (await sql()`select identifier from verification
      where identifier like 'reset-password:%' and value = ${userId}
      order by created_at desc limit 1`) as { identifier: string }[];
  expect(rows.length).toBe(1);
  return rows[0].identifier.replace("reset-password:", "");
}

async function userIdByEmail(email: string): Promise<string> {
  const rows = (await sql()`select id from users where email = ${email} limit 1`) as { id: string }[];
  expect(rows.length).toBe(1);
  return rows[0].id;
}

/**
 * The unsigned token part of a session cookie Better Auth issued. The cookie
 * value is signed — `<token>.<HMAC signature>`, URL-encoded (better-call's
 * signCookieValue) — so decode it and take everything before the first dot.
 * Never hand-roll the signature; a raw `session.token` straight from the table
 * is a cookie Better Auth can't read (round 3 finding 2).
 */
function tokenOf(cookie: string): string {
  const match = cookie.match(/(?:^|;\s*)(?:__Secure-)?better-auth\.session_token=([^;]+)/);
  expect(match).not.toBeNull();
  return decodeURIComponent(match![1]).split(".")[0];
}

/** The email whose user owns the session row for `token`. */
async function sessionOwnerEmail(token: string): Promise<string> {
  const rows = (await sql()`select user_id from session where token = ${token}`) as { user_id: string }[];
  expect(rows).toHaveLength(1);
  const user = (await sql()`select email from users where id = ${rows[0].user_id}`) as { email: string }[];
  expect(user).toHaveLength(1);
  return user[0].email;
}

/** The one-time URL from the print-mode mail line — what the user actually receives. */
function mailLink(mailLines: string[]): string {
  expect(mailLines.length).toBe(1);
  const link = mailLines[0].match(/https?:\/\/\S+/)?.[0];
  expect(link).toBeTruthy();
  return link as string;
}

async function invite(email: string, cookie: string, origin = BASE): Promise<{ status: number; json: unknown }> {
  const headers: Record<string, string> = { "content-type": "application/json", cookie };
  if (origin) headers.origin = origin;
  const res = await adminInvite(new Request(`${BASE}/api/admin/invite`, { method: "POST", headers, body: JSON.stringify({ email }) }));
  return { status: res.status, json: await res.json().catch(() => null) };
}

// Shared across the file's tests, filled in order (vitest runs them serially).
let adminCookie = "";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("accounts on a real branch", () => {
  it("the origin and CSRF checks are on: vitest's TEST env must not leak in (round 3 finding 1)", async () => {
    // tests/db/setup.ts deletes the TEST=true vitest sets in every worker;
    // without that, Better Auth's isTest() turns skipOriginCheck on and the
    // forged-Origin test below would pass for the wrong reason (200, no check
    // run). Prove the checks are really enabled before exercising them.
    const context = await AUTH.$context;
    expect(context.skipOriginCheck).toBe(false);
    expect(context.skipCSRFCheck).toBe(false);
  });

  it("refuses public sign-up", async () => {
    const r = await api("POST", "/api/auth/sign-up/email", {
      body: { email: "signup@example.com", password: "secret-123", name: "Signup" },
    });
    expect(r.status).toBe(400);
    expect(r.json).toMatchObject({ code: "EMAIL_PASSWORD_SIGN_UP_DISABLED" });
    const rows = (await sql()`select id from users where email = 'signup@example.com'`) as unknown[];
    expect(rows).toEqual([]);
  });

  it("forgot-password on an unknown address answers the same and mails nothing", async () => {
    const capture = captureMail();
    const r = await api("POST", "/api/auth/request-password-reset", {
      body: { email: "nobody@example.com", redirectTo: "/reset-password" },
    });
    expect(r.status).toBe(200);
    expect(r.json).toMatchObject({ status: true });
    expect(String((r.json as { message: string }).message)).toContain("If this email exists");
    expect(capture.mail()).toEqual([]);
    const rows = (await sql()`select id from verification`) as unknown[];
    expect(rows).toEqual([]);
    capture.restore();
  });

  it("first admin: the script upserts the admin, and the app boots it with a password and an admin session", async () => {
    const email = "admin@example.com";
    const run = spawnSync("node", ["scripts/first-admin.mjs", email], {
      cwd: process.cwd(),
      env: process.env,
      encoding: "utf8",
    });
    expect(run.status).toBe(0);
    expect(run.stdout).toContain("First admin ready");
    const rows = (await sql()`select role from users where email = ${email}`) as { role: string }[];
    expect(rows).toEqual([{ role: "admin" }]);

    // No password yet, no credential account: the email is invite wording
    // (review item 8) and the token works once.
    const capture = captureMail();
    const forgot = await api("POST", "/api/auth/request-password-reset", {
      body: { email, redirectTo: "/reset-password" },
    });
    expect(forgot.status).toBe(200);
    const mailLines = capture.mail();
    expect(mailLines.length).toBe(1);
    expect(mailLines[0]).toContain("[mail:print]");
    expect(mailLines[0]).toContain("subject=Set up");
    expect(mailLines[0]).toContain("invited");
    capture.restore();

    const token = await latestResetToken((await userIdByEmail(email)) as string);
    const set = await api("POST", "/api/auth/reset-password", { body: { newPassword: "AdminPass1", token } });
    expect(set.status).toBe(200);
    expect(set.json).toEqual({ status: true });
    // Works once: the same token is refused the second time.
    const again = await api("POST", "/api/auth/reset-password", { body: { newPassword: "AdminPass1", token } });
    expect(again.status).toBe(400);

    adminCookie = await signInCookie(email, "AdminPass1");
    const session = await api("GET", "/api/auth/get-session", { cookie: adminCookie });
    expect((session.json as { user: { role?: string; email: string } }).user).toMatchObject({ email, role: "admin" });
  });

  it("admin invite: new user created, invite wording, token works once, session role is user", async () => {
    expect(adminCookie).not.toBe("");
    const email = "invite-user@example.com";
    const capture = captureMail();
    const pre = await invite(email, adminCookie);
    expect(pre.status).toBe(200);
    const mailLines = capture.mail();
    expect(mailLines.length).toBe(1);
    expect(mailLines[0]).toContain("to=");
    expect(mailLines[0]).toContain("subject=Set up");
    expect(mailLines[0]).toContain("invited");
    capture.restore();

    const userId = await userIdByEmail(email);
    const creds = (await sql()`select password from account where user_id = ${userId}`) as unknown[];
    expect(creds).toEqual([]); // no password hash until the invitee sets one
    const token = await latestResetToken(userId);
    const set = await api("POST", "/api/auth/reset-password", { body: { newPassword: "UserPass1", token } });
    expect(set.status).toBe(200);
    const again = await api("POST", "/api/auth/reset-password", { body: { newPassword: "UserPass1", token } });
    expect(again.status).toBe(400);

    const cookie = await signInCookie(email, "UserPass1");
    const session = await api("GET", "/api/auth/get-session", { cookie });
    expect((session.json as { user: { role?: string; email: string } }).user).toMatchObject({ email, role: "user" });
  });

  it("the emailed link works as sent: GET /api/auth/reset-password/<token> redirects to the form page (code review round 1 finding 4)", async () => {
    const email = "email-link@example.com";
    const capture = captureMail();
    expect((await invite(email, adminCookie)).status).toBe(200);
    const link = mailLink(capture.mail());
    capture.restore();

    // 1.7.14 emails {baseURL}/api/auth/reset-password/<token>?callbackURL=…,
    // where baseURL already includes /api/auth. Better Auth's own GET endpoint
    // serves that path — the app's [token] page is never reached — so follow
    // the exact link the user receives, through the same handler.
    const { pathname, search } = new URL(link);
    expect(pathname).toMatch(/^\/api\/auth\/reset-password\//);
    const userId = await userIdByEmail(email);
    const token = await latestResetToken(userId);

    const clicked = await api("GET", `${pathname}${search}`);
    expect(clicked.status).toBeGreaterThanOrEqual(300);
    expect(clicked.status).toBeLessThan(400);
    expect(clicked.location).toBeTruthy();
    const target = new URL(clicked.location as string, BASE);
    expect(target.pathname).toBe("/reset-password");
    expect(target.searchParams.get("token")).toBe(token);

    // A token that is missing or already used redirects to the form with
    // ?error=INVALID_TOKEN, which the offline page test asserts shows the
    // "invalid or expired" message.
    const bad = await api("GET", "/api/auth/reset-password/not-a-real-token?callbackURL=%2Freset-password");
    expect(bad.status).toBeGreaterThanOrEqual(300);
    expect(bad.status).toBeLessThan(400);
    const badTarget = new URL(bad.location as string, BASE);
    expect(badTarget.pathname).toBe("/reset-password");
    expect(badTarget.searchParams.get("error")).toBe("INVALID_TOKEN");
  });

  it("inviting an existing address changes no row, voids the old link, sends a working fresh one", async () => {
    const email = "invite-user@example.com"; // exists from the previous test
    const userId = await userIdByEmail(email);
    // A live reset link that the re-invite must void:
    const forgotten = await api("POST", "/api/auth/request-password-reset", {
      body: { email, redirectTo: "/reset-password" },
    });
    expect(forgotten.status).toBe(200);
    const oldToken = await latestResetToken(userId);

    const capture = captureMail();
    const before = (await sql()`select count(*)::int as n from users where email = ${email}`) as { n: number }[];
    const rer = await invite(email, adminCookie);
    expect(rer.status).toBe(200);
    expect(rer.json).toEqual({ ok: true, message: "Invite sent" });
    const after = (await sql()`select count(*)::int as n from users where email = ${email}`) as { n: number }[];
    expect(after[0].n).toBe(before[0].n); // no new row (review item 7)
    const role = (await sql()`select role from users where email = ${email}`) as { role: string }[];
    expect(role).toEqual([{ role: "user" }]); // unchanged role
    // The user has a credential account now, so this is a reset email.
    const mailLines = capture.mail();
    expect(mailLines.length).toBe(1);
    expect(mailLines[0]).toContain("subject=Reset");
    capture.restore();

    const oldUse = await api("POST", "/api/auth/reset-password", { body: { newPassword: "Whatever1", token: oldToken } });
    expect(oldUse.status).toBe(400); // the old link was voided
    const freshToken = await latestResetToken(userId);
    expect(freshToken).not.toBe(oldToken);
    const freshUse = await api("POST", "/api/auth/reset-password", { body: { newPassword: "FreshPass1", token: freshToken } });
    expect(freshUse.status).toBe(200);
  });

  it("re-inviting sends a fresh link and voids the previous one", async () => {
    const email = "reinvite@example.com";
    const one = await invite(email, adminCookie);
    expect(one.status).toBe(200);
    const userId = await userIdByEmail(email);
    const oldToken = await latestResetToken(userId);

    const two = await invite(email, adminCookie);
    expect(two.status).toBe(200);
    const newToken = await latestResetToken(userId);
    expect(newToken).not.toBe(oldToken);

    const oldUse = await api("POST", "/api/auth/reset-password", { body: { newPassword: "Whatever1", token: oldToken } });
    expect(oldUse.status).toBe(400);
    const newUse = await api("POST", "/api/auth/reset-password", { body: { newPassword: "Reinvite1", token: newToken } });
    expect(newUse.status).toBe(200);
  });

  it("refuses an expired token", async () => {
    const email = "expired-link@example.com";
    expect((await invite(email, adminCookie)).status).toBe(200);
    const userId = await userIdByEmail(email);
    const token = await latestResetToken(userId);
    await sql()`update verification set expires_at = now() - interval '1 minute'
        where identifier = ${`reset-password:${token}`}`;
    const use = await api("POST", "/api/auth/reset-password", { body: { newPassword: "Expired1", token } });
    expect(use.status).toBe(400);
    expect(use.json).toMatchObject({ code: "INVALID_TOKEN" });
  });

  it("a password reset revokes sessions minted before it (round 2 item 5)", async () => {
    const email = "revoke-session@example.com";
    expect((await invite(email, adminCookie)).status).toBe(200);
    const userId = await userIdByEmail(email);
    const token = await latestResetToken(userId);
    expect((await api("POST", "/api/auth/reset-password", { body: { newPassword: "FirstPass1", token } })).status).toBe(200);

    const beforeReset = await signInCookie(email, "FirstPass1");
    const beforeSession = await api("GET", "/api/auth/get-session", { cookie: beforeReset });
    expect(beforeSession.json).toMatchObject({ session: expect.anything(), user: expect.anything() });

    const forgot = await api("POST", "/api/auth/request-password-reset", {
      body: { email, redirectTo: "/reset-password" },
    });
    expect(forgot.status).toBe(200);
    const resetToken = await latestResetToken(userId);
    const reset = await api("POST", "/api/auth/reset-password", { body: { newPassword: "SecondPass1", token: resetToken } });
    expect(reset.status).toBe(200);

    // The pre-reset session no longer resolves…
    const stale = await api("GET", "/api/auth/get-session", { cookie: beforeReset });
    expect(stale.json).toBeNull();
    // …and the new password signs in.
    const cookie = await signInCookie(email, "SecondPass1");
    const session = await api("GET", "/api/auth/get-session", { cookie });
    expect(session.json).toMatchObject({ session: expect.anything(), user: expect.anything() });
    expect((session.json as { user: { email: string } }).user.email).toBe(email);
  });

  it("role check: a signed-in user's invite is refused, the admin's succeeds (guards are layered)", async () => {
    const userCookie = await signInCookie("invite-user@example.com", "FreshPass1");
    expect((await invite("blocked@example.com", userCookie)).status).toBe(403);
    expect((await invite("blocked@example.com", "")).status).toBe(401);
    expect((await invite("role-check@example.com", adminCookie)).status).toBe(200);
  });

  it("scoping: each session token resolves only to its own user", async () => {
    const adminSession = await api("GET", "/api/auth/get-session", { cookie: adminCookie });
    expect((adminSession.json as { user: { email: string } }).user.email).toBe("admin@example.com");
    const userCookie = await signInCookie("reinvite@example.com", "Reinvite1");
    const userSession = await api("GET", "/api/auth/get-session", { cookie: userCookie });
    expect((userSession.json as { user: { email: string } }).user.email).toBe("reinvite@example.com");
    expect((userSession.json as { user: { role?: string } }).user.role).toBe("user");
    // A cross-run through the invite surface with a user cookie is refused
    // above; here the cookie tokens themselves key to their own users.
    const adminToken = tokenOf(adminCookie);
    const userToken = tokenOf(userCookie);
    expect(adminToken).not.toBe(userToken);
    expect(await sessionOwnerEmail(adminToken)).toBe("admin@example.com");
    expect(await sessionOwnerEmail(userToken)).toBe("reinvite@example.com");
  });

  it("refuses a forged-Origin sign-in POST (Better Auth's origin check)", async () => {
    // Runs before the rate-limit test on purpose: this attempt consumes the
    // shared sign-in bucket, so the limit test must come last.
    const r = await api("POST", "/api/auth/sign-in/email", {
      body: { email: "admin@example.com", password: "AdminPass1" },
      cookie: adminCookie, // cookies present → the origin check must run
      origin: "https://evil.example",
    });
    expect(r.status).toBe(403);
    expect(r.json).toMatchObject({ code: "INVALID_ORIGIN" });
  });

  it("refuses a cross-origin invite POST even with an admin session (the route's own check)", async () => {
    const r = await invite("cross-origin@example.com", adminCookie, "https://evil.example");
    expect(r.status).toBe(403);
    const rows = (await sql()`select id from users where email = 'cross-origin@example.com'`) as unknown[];
    expect(rows).toEqual([]);
  });

  it("rate limits sign-ins: enough failures in the window → the next is refused (429)", async () => {
    // The harness has no client IP (D11 open), so every /sign-in/email request
    // shares the single bucket the plan expects (review item 4): 10 per 15
    // minutes. Earlier successful sign-ins used some of it; keep trying until
    // the bucket refuses, bounded so the test can't hang. Runs last on
    // purpose: once the bucket is full, every later sign-in would be refused.
    const email = "admin@example.com";
    const statuses: number[] = [];
    for (let i = 0; i < 20; i++) {
      const r = await api("POST", "/api/auth/sign-in/email", {
        body: { email, password: "wrong-password-for-sure" },
      });
      statuses.push(r.status);
      if (r.status === 429) break;
      // A failed sign-in is 401 INVALID_EMAIL_OR_PASSWORD until the limiter
      // starts refusing.
      expect(r.status).toBe(401);
    }
    expect(statuses).toContain(429);
    expect(statuses.filter((s) => s === 401).length).toBeGreaterThanOrEqual(1);
  });
});