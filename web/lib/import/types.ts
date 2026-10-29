import type { NeonDatabase } from "drizzle-orm/neon-serverless";
import * as schema from "@/db/schema";

// Shared types for the import's database layer: the WebSocket-Pool Drizzle
// database (web/lib/db.ts's poolDb) and its transaction client.
//
// The parsers build rows with each table's real insert type
// (`typeof table.$inferInsert`), so column names AND value types are checked
// against the schema: timestamps as `Date` (Drizzle's `timestamp()` columns are
// in date mode — `PgTimestamp.mapToDriverValue` calls `toISOString()`), numerics
// as `string` (the schema's `numeric(...)` columns are mode "string"), and
// integers / bigints as `number`. The parsers convert at their boundary
// (`maybeDate`, `maybeDecimal`, `maybeInt` in validate.ts); a cast appears only
// where a value cannot be proven non-null, with a comment saying why.

export type ImportDb = NeonDatabase<typeof schema>;
export type ImportTx = Parameters<Parameters<NeonDatabase<typeof schema>["transaction"]>[0]>[0];