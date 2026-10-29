import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import { Pool } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import { drizzle as drizzlePool, type NeonDatabase } from "drizzle-orm/neon-serverless";
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

// Neon's WebSocket `Pool`, exposed for the one place an interactive transaction is needed: the
// import (task 008), which writes one transaction per commit (ADR-0025). `pg` stays a
// devDependency for the test harness only. Node 22+ provides the global WebSocket the Pool needs,
// so no neonConfig.webSocketConstructor override. One pool, cached like `db()`.
let pool: Pool | undefined;
let poolDatabase: NeonDatabase<typeof schema> | undefined;

export function poolDb() {
  if (!poolDatabase) {
    const { postgres } = parseEnv(config, ["DATABASE_URL"]);
    pool = new Pool({ connectionString: postgres.databaseUrl });
    poolDatabase = drizzlePool(pool, { schema });
  }
  return poolDatabase;
}

export async function closePool() {
  if (pool) {
    await pool.end();
    pool = undefined;
    poolDatabase = undefined;
  }
}