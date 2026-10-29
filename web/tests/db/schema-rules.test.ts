import { eq } from "drizzle-orm";
import { describe, expect, it } from "vitest";
import {
  alerts,
  analysisJobs,
  announcements,
  settings,
  stocks,
  users,
  watchlistItems,
  watchedSymbols,
} from "@/db/schema";
import { db, sql } from "@/lib/db";

// The constraints that carry rules (docs/db.md), asserted on a real, migrated,
// throwaway Neon branch (npm run test:db). Each test creates its own parent
// rows with unique values; the branch is empty before the first test.

let sequence = 0;
function unique(prefix: string) {
  sequence += 1;
  return `${prefix}${Date.now()}_${sequence}`;
}

async function insertUser(email: string) {
  const [row] = await db().insert(users).values({ email }).returning({ id: users.id });
  return row.id;
}

async function insertStock(symbol: string) {
  await db().insert(stocks).values({ symbol, name: `Stock ${symbol}`, active: true });
}

/** Resolves to the Postgres error a violating statement throws, or undefined. */
async function captureViolation(promise: Promise<unknown>) {
  try {
    await promise;
    return undefined;
  } catch (error) {
    return error as { code?: string; message?: string };
  }
}

async function partialUniqueIndexName(table: string) {
  const rows = await sql()`
    select i.relname as index_name
    from pg_class t
    join pg_index ix on ix.indrelid = t.oid
    join pg_class i on i.oid = ix.indexrelid
    where t.relname = ${table} and ix.indisunique and ix.indpred is not null
  `;
  expect(rows.length).toBe(1);
  return rows[0].index_name as string;
}

async function uniqueIndexNameFor(table: string, column: string) {
  const rows = await sql()`
    select i.relname as index_name
    from pg_class t
    join pg_index ix on ix.indrelid = t.oid
    join pg_class i on i.oid = ix.indexrelid
    join pg_attribute a on a.attrelid = t.oid and a.attnum = any(ix.indkey)
    where t.relname = ${table} and ix.indisunique and ix.indpred is null
      and a.attname = ${column}
  `;
  expect(rows.length).toBeGreaterThan(0);
  return rows[0].index_name as string;
}

describe("schema rules on a real branch", () => {
  it("fails to queue two jobs for one stock (partial unique index, 23505)", async () => {
    const symbol = unique("JOBQ_");
    await insertStock(symbol);
    await db().insert(analysisJobs).values({ symbol, status: "queued", reason: "new" });

    const indexName = await partialUniqueIndexName("analysis_jobs");
    const violation = await captureViolation(
      db().insert(analysisJobs).values({ symbol, status: "queued", reason: "new" }),
    );
    expect(violation?.code).toBe("23505");
    expect(violation?.message).toContain(indexName);
  });

  it("fails a queued job while another is running for the same stock", async () => {
    const symbol = unique("JOBR_");
    await insertStock(symbol);
    await db().insert(analysisJobs).values({ symbol, status: "running", reason: "refresh" });

    const indexName = await partialUniqueIndexName("analysis_jobs");
    const violation = await captureViolation(
      db().insert(analysisJobs).values({ symbol, status: "queued", reason: "new" }),
    );
    expect(violation?.code).toBe("23505");
    expect(violation?.message).toContain(indexName);
  });

  it("allows a new queued job once the previous one is done", async () => {
    const symbol = unique("JOBD_");
    await insertStock(symbol);
    const [job] = await db()
      .insert(analysisJobs)
      .values({ symbol, status: "queued", reason: "new" })
      .returning({ id: analysisJobs.id });
    await db().update(analysisJobs).set({ status: "done" }).where(eq(analysisJobs.id, job.id));

    await db().insert(analysisJobs).values({ symbol, status: "queued", reason: "refresh" });
    const [queued] = await db()
      .select({ status: analysisJobs.status })
      .from(analysisJobs)
      .where(eq(analysisJobs.symbol, symbol));
    expect(queued.status).toBe("queued");
  });

  it("rejects a duplicate alert dedupe_key (23505)", async () => {
    const symbol = unique("ALRT_");
    await insertStock(symbol);
    const dedupeKey = `${symbol}:pledge_up:2026-09-30`;
    const values = {
      symbol,
      kind: "pledge_up" as const,
      severity: "warning" as const,
      title: "Promoter pledge up",
      dedupeKey,
    };
    await db().insert(alerts).values(values);

    const indexName = await uniqueIndexNameFor("alerts", "dedupe_key");
    const violation = await captureViolation(db().insert(alerts).values(values));
    expect(violation?.code).toBe("23505");
    expect(violation?.message).toContain(indexName);
  });

  it("rejects a duplicate announcement exchange_ref (23505)", async () => {
    const symbol = unique("ANNC_");
    await insertStock(symbol);
    const exchangeRef = `NSE-${Date.now()}-${sequence}`;
    const values = {
      symbol,
      exchangeRef,
      announcedAt: new Date("2026-09-30T09:30:00Z"),
      subject: "Results",
      title: "Quarterly results",
    };
    await db().insert(announcements).values(values);

    const indexName = await uniqueIndexNameFor("announcements", "exchange_ref");
    const violation = await captureViolation(db().insert(announcements).values(values));
    expect(violation?.code).toBe("23505");
    expect(violation?.message).toContain(indexName);
  });

  it("returns each watched symbol once across users in watched_symbols", async () => {
    const symbol = unique("WATC_");
    await insertStock(symbol);
    const suffix = symbol.toLowerCase();
    const u1 = await insertUser(`watch1-${suffix}@example.com`);
    const u2 = await insertUser(`watch2-${suffix}@example.com`);
    await db().insert(watchlistItems).values([
      { userId: u1, symbol },
      { userId: u2, symbol },
    ]);

    const rows = await db().select().from(watchedSymbols);
    const forSymbol = rows.filter((row) => row.symbol === symbol);
    expect(forSymbol).toHaveLength(1);
  });

  it("seeds exactly the decided settings rows, with no platform-cap row", async () => {
    const rows = await db().select().from(settings);
    const byKey = Object.fromEntries(rows.map((row) => [row.key, row.value]));
    expect(byKey).toEqual({
      ask_daily_limit_per_user: 5,
      analysis_monthly_limit_per_user: 3,
      analysis_refresh_after_days: 30,
    });
    expect(Object.keys(byKey)).not.toContain("analysis_daily_limit_platform");
  });

  it("cascades a user delete to their watchlist items", async () => {
    const symbol = unique("CASC_");
    await insertStock(symbol);
    const userId = await insertUser(`cascade-${symbol.toLowerCase()}@example.com`);
    await db().insert(watchlistItems).values({ userId, symbol });

    await db().delete(users).where(eq(users.id, userId));

    const [count] = await sql()`
      select count(*)::int as n from watchlist_items where symbol = ${symbol}
    `;
    expect(count.n).toBe(0);
  });
});