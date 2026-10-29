import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "drizzle-kit";

// Migrations run over the direct connection: PgBouncer's transaction mode (pooled
// DATABASE_URL) breaks session state (ADR-0025). `generate` needs no connection,
// so the config must load even when the variable is unset (the CI drift check
// runs `generate` without it).
if (existsSync(resolve(process.cwd(), ".env.local"))) {
  process.loadEnvFile(resolve(process.cwd(), ".env.local"));
}

export default defineConfig({
  dialect: "postgresql",
  schema: "./db/schema.ts",
  out: "./db/migrations",
  dbCredentials: {
    url: process.env.DATABASE_URL_UNPOOLED ?? "",
  },
});