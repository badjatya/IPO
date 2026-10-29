import type { NeonDatabase } from "drizzle-orm/neon-serverless";
import * as schema from "@/db/schema";

// Shared types for the import's database layer: the WebSocket-Pool Drizzle
// database (web/lib/db.ts's poolDb) and its transaction client.

export type ImportDb = NeonDatabase<typeof schema>;
export type ImportTx = Parameters<Parameters<NeonDatabase<typeof schema>["transaction"]>[0]>[0];

// Drizzle's insert types type timestamps as `Date` and `numeric` as `string`,
// but the import passes the file's values through verbatim — ISO strings with
// their offsets for timestamps, numbers for numerics (Postgres accepts both).
// `Loose<T>` widens every column value so the parsers can build rows from JSON;
// column names stay fully type-checked, enum values are validated by
// `checkEnum` at runtime, and the rows are cast back to the table's insert type
// at the parser boundary.

export type Loose<T> = {
  [K in keyof T]?:
    | string
    | number
    | boolean
    | Date
    | null
    | undefined
    | readonly unknown[]
    | { [key: string]: unknown };
};