import { neon, type NeonQueryFunction } from "@neondatabase/serverless";
import { parseEnv } from "@neon/env";
import config from "@/neon";

// Neon's HTTP driver: one-shot queries that work on any host (D11 is still open) and under
// either ORM (D03). Uses the pooled DATABASE_URL; migrations take DATABASE_URL_UNPOOLED (task 007).
let client: NeonQueryFunction<false, false> | undefined;

export function sql() {
  if (!client) {
    const { postgres } = parseEnv(config, ["DATABASE_URL"]);
    client = neon(postgres.databaseUrl);
  }
  return client;
}
