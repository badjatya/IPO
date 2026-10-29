import { and, eq, like } from "drizzle-orm";
import { users, verification } from "@/db/schema";
import { getAuth } from "@/lib/auth";
import { db } from "@/lib/db";
import { assertSameOrigin, AuthError, authErrorResponse, requireAdmin } from "@/lib/auth-guard";
import { assertMailConfig, MailNotConfiguredError } from "@/lib/mail";

// Admin-only invite (ADR-0028): create the user row (never a password) and let
// Better Auth's reset-password mechanism issue the one-time link, whose hook
// sends the email. There is deliberately no rate limit here — the role check
// plus the origin check is the gate (review item 4). The response is identical
// for a new and an existing address (review item 7).
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function handleInvite(request: Request): Promise<Response> {
  // Same-origin first: the app's own routes are outside Better Auth's origin
  // check (review item 3).
  assertSameOrigin(request);
  await requireAdmin(request.headers);

  // Mail config up front, before any row exists (round 2 item 4): the reset
  // hook fires delivery without awaiting, so a missing config must surface
  // here, not in a log after the route answered.
  assertMailConfig();

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "invalid json" }, { status: 400 });
  }
  const email = typeof body === "object" && body !== null && typeof (body as { email?: unknown }).email === "string"
    ? (body as { email: string }).email.trim().toLowerCase()
    : "";
  const name = typeof body === "object" && body !== null && typeof (body as { name?: unknown }).name === "string"
    ? (body as { name: string }).name.trim()
    : null;
  if (!EMAIL_PATTERN.test(email)) {
    return Response.json({ error: "invalid email" }, { status: 400 });
  }

  // New address → a scoped insert with no password; the invite never changes an
  // existing row's role (an invite neither demotes an admin nor promotes a
  // user, review item 7).
  const existing = await db()
    .select({ id: users.id })
    .from(users)
    .where(eq(users.email, email))
    .limit(1);
  let userId: string;
  if (existing.length > 0) {
    userId = existing[0].id;
  } else {
    const values: { email: string; role: string; name?: string } = { email, role: "user" };
    if (name) values.name = name;
    const inserted = await db().insert(users).values(values).returning({ id: users.id });
    userId = inserted[0].id;
  }

  // Void the user's outstanding links: reset rows are keyed by token, not by
  // address (`identifier = 'reset-password:<token>'`, `value = <user id>`), so
  // re-inviting voids the old link while a fresh one goes out (review item 7).
  await db()
    .delete(verification)
    .where(and(like(verification.identifier, "reset-password:%"), eq(verification.value, userId)));

  // The hook picks the wording (invite, since a fresh invitee has no credential
  // account) and sends the email; the response here is the same either way.
  await getAuth().api.requestPasswordReset({ body: { email, redirectTo: "/reset-password" } });

  return Response.json({ ok: true, message: "Invite sent" });
}

export async function POST(request: Request): Promise<Response> {
  try {
    return await handleInvite(request);
  } catch (error) {
    if (error instanceof AuthError) return authErrorResponse(error);
    // Checked by class, not by message text (code review round 1 finding 7).
    if (error instanceof MailNotConfiguredError) {
      return Response.json({ error: "email is not configured" }, { status: 500 });
    }
    return Response.json({ error: "internal error" }, { status: 500 });
  }
}