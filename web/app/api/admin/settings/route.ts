import { eq } from "drizzle-orm";
import { settings, users } from "@/db/schema";
import { db } from "@/lib/db";
import { assertSameOrigin, AuthError, authErrorResponse, requireAdmin } from "@/lib/auth-guard";
import { validateSettingValue } from "@/lib/settings";

// Admin settings API (task 013): GET lists every row with the updater's email
// (left join), POST edits one row only. GET is read-only, so requireAdmin alone
// guards it — there is no state to forge with a GET. POST runs the 010 order
// the auth-guard contract left for this route: same-origin first (the app's
// own routes are outside Better Auth's origin check), then the role check,
// then validate against the known keys, then write. One request, one row; no
// bulk editing, no row creation — a known key with no row (the D08 cap) is
// answered 404 and stays absent.

async function listSettings() {
  return db()
    .select({
      key: settings.key,
      value: settings.value,
      description: settings.description,
      updatedAt: settings.updatedAt,
      updatedBy: settings.updatedBy,
      updatedByEmail: users.email,
    })
    .from(settings)
    .leftJoin(users, eq(settings.updatedBy, users.id))
    .orderBy(settings.key);
}

export async function GET(request: Request): Promise<Response> {
  try {
    await requireAdmin(request.headers);
    return Response.json({ settings: await listSettings() });
  } catch (error) {
    if (error instanceof AuthError) return authErrorResponse(error);
    return Response.json({ error: "internal error" }, { status: 500 });
  }
}

export async function POST(request: Request): Promise<Response> {
  try {
    // Same-origin first, then the role check — the contract in auth-guard.ts.
    assertSameOrigin(request);
    const admin = await requireAdmin(request.headers);

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return Response.json({ error: "invalid json" }, { status: 400 });
    }
    const validated = validateSettingValue(body);
    if (!validated.ok) {
      return Response.json({ error: validated.error }, { status: 400 });
    }

    const updated = await db()
      .update(settings)
      .set({ value: validated.value, updatedAt: new Date(), updatedBy: admin.id })
      .where(eq(settings.key, validated.key))
      .returning({
        key: settings.key,
        value: settings.value,
        description: settings.description,
        updatedAt: settings.updatedAt,
        updatedBy: settings.updatedBy,
      });
    if (updated.length === 0) {
      return Response.json({ error: "settings row not found" }, { status: 404 });
    }
    // The updater is the admin who just posted, so the saved row carries their
    // email too — the page's "Changed by" line without a second query.
    return Response.json({ ok: true, settings: { ...updated[0], updatedByEmail: admin.email } });
  } catch (error) {
    if (error instanceof AuthError) return authErrorResponse(error);
    return Response.json({ error: "internal error" }, { status: 500 });
  }
}