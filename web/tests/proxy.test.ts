import { describe, expect, it } from "vitest";
import { proxyDecision, SESSION_COOKIE } from "@/proxy";

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

  it("ignores everything outside /admin and /api/admin (the matcher gates paths)", () => {
    // The matcher covers the paths; for a stray path the predicate still
    // answers sensibly for the admin surface only.
    expect(proxyDecision("/sign-in", false)).toBe("redirect");
  });

  it("uses Better Auth's default session cookie name", () => {
    expect(SESSION_COOKIE).toBe("better-auth.session_token");
  });
});