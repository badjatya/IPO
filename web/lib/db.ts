import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import { parseEnv } from "@neon/env";
import * as schema from "@/db/schema";
import config from "@/neon";

// Neon's HTTP driver: one-shot queries that work on any host (D11 is still open) and under
// either ORM (D03). Uses the pooled DATABASE_URL; migrations take DATABASE_URL_UNPOOLED (task 007).
// One connection: `db()` is Drizzle over the same cached `sql()` client, not a second connection
// (ADR-0025).
let client: NeonQueryFunction<false, false> | undefined;
let database: ReturnType<typeof drizzle> | undefined;

export function sql() {
  if (!client) {
    const { postgres } = parseEnv(config, ["DATABASE_URL"]);
    client = neon(postgres.databaseUrl);
  }
  return client;
}

export function db() {
  if (!database) {
    database = drizzle(sql(), { schema });
  }
  return database;
}