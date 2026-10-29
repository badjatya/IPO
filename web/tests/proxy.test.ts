import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import proxy, { proxyDecision } from "@/proxy";

function requestFor(path: string, cookieHeader?: string): NextRequest {
  const headers: Record<string, string> = {};
  if (cookieHeader) headers.cookie = cookieHeader;
  return new NextRequest(`http://localhost:3000${path}`, { headers });
}

function decisionOf(path: string, cookieHeader?: string) {
  return proxy(requestFor(path, cookieHeader));
}

describe("proxy predicate (review item 9)", () => {
  it("is a fast cookie check: any session cookie lets the request through", () => {
    expect(proxyDecision("/admin/invite", true)).toBe("allow");
    expect(proxyDecision("/api/admin/invite", true)).toBe("allow");
  });

  it("redirects page requests without the session cookie", () => {
    expect(proxyDecision("/admin/invite", false)).toBe("redirect");
  });

  it("answers 401 for API requests without the session cookie", () => {
    expect(proxyDecision("/api/admin/invite", false)).toBe("unauthorized");
  });
});

describe("proxy cookie check (code review round 1 finding 2)", () => {
  it("lets a request through with the plain local cookie name", async () => {
    expect((await decisionOf("/admin/invite", "better-auth.session_token=sess-1")).status).toBe(200);
  });

  it("lets a request through with the __Secure- name an https AUTH_URL sets", async () => {
    expect((await decisionOf("/admin/invite", "__Secure-better-auth.session_token=sess-1")).status).toBe(200);
  });

  it("lets an API request through with either cookie name", async () => {
    expect((await decisionOf("/api/admin/invite", "better-auth.session_token=sess-1")).status).toBe(200);
    expect((await decisionOf("/api/admin/invite", "__Secure-better-auth.session_token=sess-1")).status).toBe(200);
  });

  it("redirects page requests without a session cookie and asks for /sign-in", async () => {
    const res = await decisionOf("/admin/invite");
    expect(res.status).toBe(307);
    // `next` is URL-encoded (%2F for the leading slashes); the sign-in page
    // reads it back as /admin/invite.
    expect(res.headers.get("location")).toBe("http://localhost:3000/sign-in?next=%2Fadmin%2Finvite");
  });

  it("answers 401 JSON for API requests without a session cookie", async () => {
    const res = await decisionOf("/api/admin/invite");
    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toEqual({ error: "unauthorized" });
  });

  it("ignores an unrelated cookie alone", async () => {
    expect((await decisionOf("/admin/invite", "other_cookie=x")).status).toBe(307);
  });
});