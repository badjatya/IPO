import { getAuth } from "@/lib/auth";

// The app's only admin concept is users.role (no admin plugin, review item 1).
// These helpers carry the authoritative checks for the app's own routes; the
// proxy is only a fast cookie check and is never trusted alone (review item 9,
// CVE-2025-29927).

export interface SessionUser {
  id: string;
  email: string;
  role: string | null;
  name?: string | null;
}

/** A guard failure with the HTTP status the route should answer (401/403). */
export class AuthError extends Error {
  constructor(
    public readonly status: 401 | 403,
    message: string,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

/** The signed-in user's row, or null. Reads the session from the request headers. */
export async function getSessionUser(headers: Headers): Promise<SessionUser | null> {
  const session = await getAuth().api.getSession({ headers });
  if (!session) return null;
  const user = session.user as { role?: string | null };
  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name ?? null,
    // role is read through additionalFields; the wide Better Auth type does
    // not know it, but the DB column always carries a value.
    role: user.role ?? null,
  };
}

/**
 * The admin-only gate for routes: no session → 401, any other role → 403.
 * Returns the user row, or throws AuthError with the right status.
 */
export async function requireAdmin(headers: Headers): Promise<SessionUser> {
  const user = await getSessionUser(headers);
  if (!user) throw new AuthError(401, "sign in required");
  if (user.role !== "admin") throw new AuthError(403, "admin only");
  return user;
}

/** Turn an AuthError into its HTTP response; anything else rethrows. */
export function authErrorResponse(error: unknown): Response {
  if (error instanceof AuthError) {
    return Response.json({ error: error.message }, { status: error.status });
  }
  throw error;
}

/**
 * Same-origin check for the app's own cookie-authenticated routes (review
 * item 3): Better Auth's origin check covers only /api/auth/*, so the app's
 * routes check `Origin` against the AUTH_URL origin themselves — 013's
 * settings route must call this too.
 */
export function assertSameOrigin(request: Request): void {
  const origin = request.headers.get("origin");
  const allowed = new URL(process.env.AUTH_URL ?? "http://localhost:3000").origin;
  if (origin !== allowed) {
    throw new AuthError(403, "cross-origin request refused");
  }
}