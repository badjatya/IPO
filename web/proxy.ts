import { NextRequest, NextResponse } from "next/server";

// Next 16.4's middleware replacement (web/proxy.ts, runs on Node, review item
// 9). This is deliberately only a fast cookie check — pages and API routes
// carry the authoritative session-and-role checks (admin layout + requireAdmin),
// so a middleware bypass (CVE-2025-29927 class) never exposes the admin
// surface.

// Better Auth's default session cookie name; the app sets no cookiePrefix.
export const SESSION_COOKIE = "better-auth.session_token";

export type ProxyDecision = "allow" | "redirect" | "unauthorized";

/** Pure predicate: what should the proxy do for this path + cookie? */
export function proxyDecision(pathname: string, hasSessionCookie: boolean): ProxyDecision {
  if (hasSessionCookie) return "allow";
  return pathname.startsWith("/api/admin") ? "unauthorized" : "redirect";
}

export default function proxy(request: NextRequest) {
  const decision = proxyDecision(request.nextUrl.pathname, request.cookies.has(SESSION_COOKIE));
  if (decision === "allow") return NextResponse.next();
  if (decision === "unauthorized") {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const signIn = new URL("/sign-in", request.url);
  signIn.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signIn);
}

export const config = {
  matcher: ["/admin/:path*", "/api/admin/:path*"],
};