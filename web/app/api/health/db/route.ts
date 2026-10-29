import { sql } from "@/lib/db";

// Read at request time, never at build.
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const [row] = await sql()`select 1 as ok, current_database() as database, version() as version`;
    return Response.json({ ok: row.ok === 1, database: row.database, version: row.version });
  } catch (error) {
    console.error("database health check failed", error);
    return Response.json({ ok: false }, { status: 503 });
  }
}
