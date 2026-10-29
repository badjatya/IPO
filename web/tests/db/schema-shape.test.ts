import { describe, expect, it } from "vitest";
import { sql } from "@/lib/db";

// The full schema, read from pg_catalog / information_schema after migrate:
// the 23 tables, the 12 enums with their values, the watched_symbols view, the
// partial unique indexes, the unique exchange_ref/dedupe_key indexes and the
// composite FKs (docs/db.md). Read from the catalogs rather than by name, so
// drizzle's naming never bitrots the checks.

const baseTables = [
  "ai_questions",
  "alerts",
  "analysis_job_events",
  "analysis_jobs",
  "analysis_requests",
  "announcements",
  "imports",
  "ipo_analyses",
  "ipo_cards",
  "ipo_outcomes",
  "ipo_snapshots",
  "ipo_subscriptions",
  "ipo_verdicts",
  "ipos",
  "quarterly_results",
  "reports",
  "settings",
  "shareholding",
  "stock_analyses",
  "stock_quotes",
  "stocks",
  "users",
  "watchlist_items",
];

const enums: Record<string, string[]> = {
  ipo_phase: ["announced", "upcoming", "open", "closing_today", "awaiting_listing", "listing_today", "listed"],
  verdict: ["apply", "listing_gains", "neutral", "avoid", "pending"],
  anchor_grade: ["strong", "average", "weak", "pending"],
  card_source: ["rhp", "web"],
  rhp_source: ["nse", "sebi"],
  report_session: ["AM", "PM"],
  sub_category: ["qib", "nii", "snii", "bnii", "retail", "employee", "total"],
  importance: ["high", "medium", "low", "routine"],
  job_status: ["queued", "running", "done", "failed"],
  analysis_served: ["saved", "new", "refresh"],
  alert_kind: ["results", "announcement", "pledge_up", "promoter_down", "fii_move", "dii_move"],
  severity: ["info", "watch", "warning"],
};

// Quotes stripped, so the checks don't depend on pg_get_indexdef's quoting style.
function unquoted(definition: string) {
  return definition.replaceAll('"', "");
}

// db.md's primary keys: composite for the natural-key tables, a single column
// for the rest, `id` for the identity and uuid tables. These are what make
// re-importing the same file update the same row (db.md principle 2).
const primaryKeys: Record<string, string[]> = {
  ai_questions: ["id"],
  alerts: ["id"],
  analysis_job_events: ["id"],
  analysis_jobs: ["id"],
  analysis_requests: ["id"],
  announcements: ["id"],
  imports: ["commit_sha"],
  ipo_analyses: ["ipo_key"],
  ipo_cards: ["ipo_key"],
  ipo_outcomes: ["ipo_key"],
  ipo_snapshots: ["ipo_key", "taken_at"],
  ipo_subscriptions: ["ipo_key", "taken_at", "category"],
  ipo_verdicts: ["report_date", "session", "ipo_key"],
  ipos: ["key"],
  quarterly_results: ["symbol", "period_end", "consolidated"],
  reports: ["report_date", "session"],
  settings: ["key"],
  shareholding: ["symbol", "quarter_end"],
  stock_analyses: ["symbol"],
  stock_quotes: ["symbol"],
  stocks: ["symbol"],
  users: ["id"],
  watchlist_items: ["user_id", "symbol"],
};

function parsePkColumns(definition: string): string[] {
  const match = definition.match(/PRIMARY KEY \(([^)]*)\)/);
  expect(match, `cannot parse primary key definition "${definition}"`).toBeTruthy();
  return match![1].split(",").map((column) => column.trim().replaceAll('"', ""));
}

describe("schema shape on a real branch", () => {
  it("has exactly the 23 db.md tables in public", async () => {
    const rows = await sql()`
      select table_name
      from information_schema.tables
      where table_schema = 'public' and table_type = 'BASE TABLE'
    `;
    expect(rows.map((row) => row.table_name as string).toSorted()).toEqual([...baseTables].toSorted());
  });

  it("has the 12 db.md enums with their values", async () => {
    const rows = await sql()`
      select t.typname as name,
             array_agg(e.enumlabel order by e.enumsortorder) as values
      from pg_type t
      join pg_enum e on e.enumtypid = t.oid
      join pg_namespace n on n.oid = t.typnamespace
      where t.typtype = 'e' and n.nspname = 'public'
      group by t.typname
    `;
    expect(Object.fromEntries(rows.map((row) => [row.name, row.values]))).toEqual(enums);
  });

  it("has the watched_symbols view (distinct symbols, no user data)", async () => {
    const rows = await sql()`
      select table_name from information_schema.views where table_schema = 'public'
    `;
    expect(rows.map((row) => row.table_name)).toContain("watched_symbols");
  });

  it("has the partial unique indexes that carry the rules", async () => {
    const rows = await sql()`
      select t.relname as table_name, pg_get_indexdef(i.oid) as definition
      from pg_class t
      join pg_index ix on ix.indrelid = t.oid
      join pg_class i on i.oid = ix.indexrelid
      join pg_namespace n on n.oid = t.relnamespace
      where n.nspname = 'public' and ix.indisunique and ix.indpred is not null
    `;
    const defs = rows.map((row) => unquoted(row.definition as string));
    expect(
      defs.find((d) =>
        d.includes("ON analysis_jobs USING btree (symbol) WHERE analysis_jobs.status in ('queued', 'running')"),
      ),
    ).toBeTruthy();
    expect(
      defs.find((d) => d.includes("ON ipos USING btree (symbol) WHERE ipos.symbol is not null")),
    ).toBeTruthy();
    expect(
      defs.find((d) => d.includes("ON stocks USING btree (isin) WHERE stocks.isin is not null")),
    ).toBeTruthy();
  });

  it("has the unique exchange_ref and dedupe_key indexes", async () => {
    const rows = await sql()`
      select t.relname as table_name,
             a.attname as column_name,
             pg_get_indexdef(i.oid) as definition
      from pg_class t
      join pg_index ix on ix.indrelid = t.oid
      join pg_class i on i.oid = ix.indexrelid
      join pg_namespace n on n.oid = t.relnamespace
      join pg_attribute a on a.attrelid = t.oid and a.attnum = any(ix.indkey)
      where n.nspname = 'public' and ix.indisunique and ix.indpred is null
        and t.relname in ('announcements', 'alerts')
    `;
    const byColumn = new Map(
      rows.map((row) => [`${row.table_name}.${row.column_name}`, unquoted(row.definition as string)]),
    );
    const exchangeRef = byColumn.get("announcements.exchange_ref");
    expect(exchangeRef).toBeTruthy();
    expect(exchangeRef).toMatch(/^CREATE UNIQUE INDEX /);
    const dedupeKey = byColumn.get("alerts.dedupe_key");
    expect(dedupeKey).toBeTruthy();
    expect(dedupeKey).toMatch(/^CREATE UNIQUE INDEX /);
  });

  it("has the composite FKs (ipo_subscriptions, ipo_verdicts)", async () => {
    const rows = await sql()`
      select pg_get_constraintdef(con.oid) as definition
      from pg_constraint con
      join pg_namespace n on n.oid = con.connamespace
      where con.contype = 'f' and n.nspname = 'public'
    `;
    const defs = rows.map((row) => unquoted(row.definition as string));
    expect(
      defs.find((d) =>
        /FOREIGN KEY \(ipo_key, taken_at\) REFERENCES (public\.)?ipo_snapshots \(ipo_key, taken_at\)/.test(d),
      ),
    ).toBeTruthy();
    expect(
      defs.find((d) =>
        /FOREIGN KEY \(report_date, session\) REFERENCES (public\.)?reports \(report_date, session\)/.test(d),
      ),
    ).toBeTruthy();
  });

  it("has exactly one primary key per table, with db.md's columns", async () => {
    const rows = await sql()`
      select c.relname as table_name, pg_get_constraintdef(con.oid) as definition
      from pg_constraint con
      join pg_class c on c.oid = con.conrelid
      join pg_namespace n on n.oid = c.relnamespace
      where con.contype = 'p' and n.nspname = 'public'
    `;
    const byTable = new Map(
      rows.map((row) => [row.table_name as string, unquoted(row.definition as string)]),
    );
    // One row per table means exactly one primary key each: a second `PRIMARY
    // KEY` clause would make the build fail, and a dropped key shows up here.
    expect([...byTable.keys()].toSorted()).toEqual([...baseTables].toSorted());
    for (const table of baseTables) {
      expect(parsePkColumns(byTable.get(table)!)).toEqual(primaryKeys[table]);
    }
  });
});