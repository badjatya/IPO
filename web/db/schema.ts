import { sql } from "drizzle-orm";
import { desc, relations } from "drizzle-orm";
import {
  bigint,
  boolean,
  customType,
  date,
  foreignKey,
  index,
  integer,
  jsonb,
  numeric,
  pgEnum,
  pgTable,
  pgView,
  primaryKey,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

// The schema mirrors docs/db.md exactly. Money is numeric(12,2) or numeric(14,2)
// (₹ crore), percentages numeric(7,2), P/E and subscription times numeric(10,2).
// Times are timestamptz, dates are date (db.md principles 5-6). Where db.md lists
// no default for a column the app fills on insert, the schema uses `default now()`
// for the time columns and `default gen_random_uuid()` for the two bare uuid keys.

// ---------------------------------------------------------------------------
// Enums (db.md § Enums)
// ---------------------------------------------------------------------------

export const ipoPhase = pgEnum("ipo_phase", [
  "announced",
  "upcoming",
  "open",
  "closing_today",
  "awaiting_listing",
  "listing_today",
  "listed",
]);

export const verdict = pgEnum("verdict", ["apply", "listing_gains", "neutral", "avoid", "pending"]);

export const anchorGrade = pgEnum("anchor_grade", ["strong", "average", "weak", "pending"]);

export const cardSource = pgEnum("card_source", ["rhp", "web"]);

export const rhpSource = pgEnum("rhp_source", ["nse", "sebi"]);

export const reportSession = pgEnum("report_session", ["AM", "PM"]);

export const subCategory = pgEnum("sub_category", [
  "qib",
  "nii",
  "snii",
  "bnii",
  "retail",
  "employee",
  "total",
]);

export const importance = pgEnum("importance", ["high", "medium", "low", "routine"]);

export const jobStatus = pgEnum("job_status", ["queued", "running", "done", "failed"]);

export const analysisServed = pgEnum("analysis_served", ["saved", "new", "refresh"]);

export const alertKind = pgEnum("alert_kind", [
  "results",
  "announcement",
  "pledge_up",
  "promoter_down",
  "fii_move",
  "dii_move",
]);

export const severity = pgEnum("severity", ["info", "watch", "warning"]);

// ---------------------------------------------------------------------------
// citext for users.email (extension created by the citext custom migration,
// which runs before the tables migration)
// ---------------------------------------------------------------------------

const citext = customType<{ data: string; driverData: string }>({
  dataType() {
    return "citext";
  },
});

// ---------------------------------------------------------------------------
// Research tables: IPOs
// ---------------------------------------------------------------------------

export const ipos = pgTable(
  "ipos",
  {
    key: text("key").primaryKey(),
    name: text("name").notNull(),
    symbol: text("symbol"),
    openDate: date("open_date"),
    closeDate: date("close_date"),
    allotmentDate: date("allotment_date"),
    listingDate: date("listing_date"),
    priceLow: numeric("price_low", { precision: 12, scale: 2 }),
    priceHigh: numeric("price_high", { precision: 12, scale: 2 }),
    lotSize: integer("lot_size"),
    issueSizeCr: numeric("issue_size_cr", { precision: 14, scale: 2 }),
    issueSizeText: text("issue_size_text"),
    faceValue: text("face_value"),
    leadManagers: text("lead_managers"),
    registrar: text("registrar"),
    rhpUrl: text("rhp_url"),
    rhpSource: rhpSource("rhp_source"),
    investorgainUrl: text("investorgain_url"),
    phase: ipoPhase("phase").notNull(),
    anchorDone: boolean("anchor_done").notNull().default(false),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("ipos_phase_index").on(table.phase),
    index("ipos_listing_date_index").on(table.listingDate),
    uniqueIndex("ipos_symbol_unique").on(table.symbol).where(sql`${table.symbol} is not null`),
  ],
);

export const ipoSnapshots = pgTable(
  "ipo_snapshots",
  {
    ipoKey: text("ipo_key").references(() => ipos.key),
    takenAt: timestamp("taken_at", { withTimezone: true }),
    phase: ipoPhase("phase").notNull(),
    gmp: numeric("gmp", { precision: 12, scale: 2 }),
    gmpLow: numeric("gmp_low", { precision: 12, scale: 2 }),
    gmpHigh: numeric("gmp_high", { precision: 12, scale: 2 }),
    gmpPct: numeric("gmp_pct", { precision: 7, scale: 2 }),
    gmpUpdated: text("gmp_updated"),
    pe: numeric("pe", { precision: 10, scale: 2 }),
    allotment: jsonb("allotment"),
    sourceFile: text("source_file").notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.ipoKey, table.takenAt] }),
    index("ipo_snapshots_taken_at_index").on(table.ipoKey, desc(table.takenAt)),
  ],
);

export const ipoSubscriptions = pgTable(
  "ipo_subscriptions",
  {
    ipoKey: text("ipo_key"),
    takenAt: timestamp("taken_at", { withTimezone: true }),
    category: subCategory("category"),
    sharesOffered: bigint("shares_offered", { mode: "number" }),
    sharesBid: bigint("shares_bid", { mode: "number" }),
    times: numeric("times", { precision: 10, scale: 2 }),
  },
  (table) => [
    primaryKey({ columns: [table.ipoKey, table.takenAt, table.category] }),
    foreignKey({
      columns: [table.ipoKey, table.takenAt],
      foreignColumns: [ipoSnapshots.ipoKey, ipoSnapshots.takenAt],
    }),
  ],
);

export const ipoCards = pgTable("ipo_cards", {
  ipoKey: text("ipo_key")
    .primaryKey()
    .references(() => ipos.key),
  source: cardSource("source").notNull(),
  analysedOn: date("analysed_on"),
  verdict: verdict("verdict").notNull(),
  verdictText: text("verdict_text").notNull(),
  summary: text("summary"),
  financials: text("financials"),
  quota: text("quota"),
  positives: text("positives").array().notNull().default(sql`'{}'`),
  redFlags: text("red_flags").array().notNull().default(sql`'{}'`),
  anchor: text("anchor"),
  anchorGrade: anchorGrade("anchor_grade").notNull(),
  aiModel: text("ai_model"),
  aiPromptVersion: text("ai_prompt_version"),
  aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
  sourceFile: text("source_file").notNull(),
});

export const ipoAnalyses = pgTable("ipo_analyses", {
  ipoKey: text("ipo_key")
    .primaryKey()
    .references(() => ipos.key),
  markdown: text("markdown").notNull(),
  rhpTextPath: text("rhp_text_path"),
  aiModel: text("ai_model"),
  aiPromptVersion: text("ai_prompt_version"),
  aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
  contentSha: text("content_sha").notNull(),
});

export const reports = pgTable(
  "reports",
  {
    reportDate: date("report_date"),
    session: reportSession("session"),
    headline: text("headline"),
    notes: text("notes").array().notNull().default(sql`'{}'`),
    quiet: boolean("quiet").notNull(),
    carriedFrom: text("carried_from"),
    aiModel: text("ai_model"),
    aiPromptVersion: text("ai_prompt_version"),
    aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
    commitSha: text("commit_sha"),
    sourceFile: text("source_file").notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.reportDate, table.session] }),
  ],
);

export const ipoVerdicts = pgTable(
  "ipo_verdicts",
  {
    reportDate: date("report_date"),
    session: reportSession("session"),
    ipoKey: text("ipo_key"),
    verdict: verdict("verdict"),
    verdictText: text("verdict_text"),
    bestCategory: text("best_category"),
    categoryNote: text("category_note"),
    overrides: jsonb("overrides"),
  },
  (table) => [
    primaryKey({ columns: [table.reportDate, table.session, table.ipoKey] }),
    foreignKey({
      columns: [table.reportDate, table.session],
      foreignColumns: [reports.reportDate, reports.session],
    }),
    foreignKey({
      columns: [table.ipoKey],
      foreignColumns: [ipos.key],
    }),
    index("ipo_verdicts_ipo_key_report_date_index").on(
      table.ipoKey,
      desc(table.reportDate),
      desc(table.session),
    ),
  ],
);

export const ipoOutcomes = pgTable("ipo_outcomes", {
  ipoKey: text("ipo_key")
    .primaryKey()
    .references(() => ipos.key),
  symbol: text("symbol").notNull(),
  listingDate: date("listing_date").notNull(),
  issuePrice: numeric("issue_price", { precision: 12, scale: 2 }).notNull(),
  listingPrice: numeric("listing_price", { precision: 12, scale: 2 }).notNull(),
  dayClose: numeric("day_close", { precision: 12, scale: 2 }),
  dayHigh: numeric("day_high", { precision: 12, scale: 2 }),
  dayLow: numeric("day_low", { precision: 12, scale: 2 }),
  listingGainPct: numeric("listing_gain_pct", { precision: 7, scale: 2 }),
  closeGainPct: numeric("close_gain_pct", { precision: 7, scale: 2 }),
  gmpEve: numeric("gmp_eve", { precision: 12, scale: 2 }),
  gmpEvePct: numeric("gmp_eve_pct", { precision: 7, scale: 2 }),
  gmpEveSnapshot: timestamp("gmp_eve_snapshot", { withTimezone: true }),
  gmpMissPts: numeric("gmp_miss_pts", { precision: 7, scale: 2 }),
  verdict: verdict("verdict"),
  verdictText: text("verdict_text"),
  bestCategory: text("best_category"),
  verdictReport: text("verdict_report"),
  anchorGrade: anchorGrade("anchor_grade"),
  pe: numeric("pe", { precision: 10, scale: 2 }),
  sizeCr: numeric("size_cr", { precision: 14, scale: 2 }),
  subQib: numeric("sub_qib", { precision: 10, scale: 2 }),
  subSnii: numeric("sub_snii", { precision: 10, scale: 2 }),
  subBnii: numeric("sub_bnii", { precision: 10, scale: 2 }),
  subRetail: numeric("sub_retail", { precision: 10, scale: 2 }),
  subTotal: numeric("sub_total", { precision: 10, scale: 2 }),
  subscriptionSource: text("subscription_source"),
  priceSource: text("price_source"),
  recordedAt: timestamp("recorded_at", { withTimezone: true }).notNull().defaultNow(),
});

// ---------------------------------------------------------------------------
// Research tables: stocks
// ---------------------------------------------------------------------------

export const stocks = pgTable(
  "stocks",
  {
    symbol: text("symbol").primaryKey(),
    isin: text("isin"),
    name: text("name").notNull(),
    industry: text("industry"),
    ipoKey: text("ipo_key").references(() => ipos.key),
    active: boolean("active").notNull(),
    lastResearchedAt: timestamp("last_researched_at", { withTimezone: true }),
  },
  (table) => [
    uniqueIndex("stocks_isin_unique").on(table.isin).where(sql`${table.isin} is not null`),
  ],
);

export const stockAnalyses = pgTable("stock_analyses", {
  symbol: text("symbol")
    .primaryKey()
    .references(() => stocks.symbol),
  summary: text("summary").notNull(),
  financials: text("financials"),
  valuation: text("valuation"),
  positives: text("positives").array().notNull().default(sql`'{}'`),
  redFlags: text("red_flags").array().notNull().default(sql`'{}'`),
  markdown: text("markdown").notNull(),
  analysedOn: date("analysed_on").notNull(),
  basedOnPeriod: date("based_on_period"),
  aiModel: text("ai_model"),
  aiPromptVersion: text("ai_prompt_version"),
  aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
  sourceFile: text("source_file").notNull(),
});

export const stockQuotes = pgTable("stock_quotes", {
  symbol: text("symbol")
    .primaryKey()
    .references(() => stocks.symbol),
  price: numeric("price", { precision: 12, scale: 2 }),
  changePct: numeric("change_pct", { precision: 7, scale: 2 }),
  week52High: numeric("week52_high", { precision: 12, scale: 2 }),
  week52Low: numeric("week52_low", { precision: 12, scale: 2 }),
  marketCapCr: numeric("market_cap_cr", { precision: 14, scale: 2 }),
  pe: numeric("pe", { precision: 10, scale: 2 }),
  asOf: timestamp("as_of", { withTimezone: true }).notNull(),
});

export const quarterlyResults = pgTable(
  "quarterly_results",
  {
    symbol: text("symbol").references(() => stocks.symbol),
    periodEnd: date("period_end"),
    consolidated: boolean("consolidated"),
    revenueCr: numeric("revenue_cr", { precision: 14, scale: 2 }),
    otherIncomeCr: numeric("other_income_cr", { precision: 14, scale: 2 }),
    expensesCr: numeric("expenses_cr", { precision: 14, scale: 2 }),
    ebitdaCr: numeric("ebitda_cr", { precision: 14, scale: 2 }),
    patCr: numeric("pat_cr", { precision: 14, scale: 2 }),
    eps: numeric("eps", { precision: 10, scale: 2 }),
    filedAt: timestamp("filed_at", { withTimezone: true }),
    sourceUrl: text("source_url"),
    aiSummary: text("ai_summary"),
    aiModel: text("ai_model"),
    aiPromptVersion: text("ai_prompt_version"),
    aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
  },
  (table) => [
    primaryKey({ columns: [table.symbol, table.periodEnd, table.consolidated] }),
    index("quarterly_results_symbol_period_end_index").on(table.symbol, desc(table.periodEnd)),
  ],
);

export const shareholding = pgTable(
  "shareholding",
  {
    symbol: text("symbol").references(() => stocks.symbol),
    quarterEnd: date("quarter_end"),
    promoterPct: numeric("promoter_pct", { precision: 7, scale: 2 }),
    fiiPct: numeric("fii_pct", { precision: 7, scale: 2 }),
    diiPct: numeric("dii_pct", { precision: 7, scale: 2 }),
    publicPct: numeric("public_pct", { precision: 7, scale: 2 }),
    otherPct: numeric("other_pct", { precision: 7, scale: 2 }),
    promoterPledgedPct: numeric("promoter_pledged_pct", { precision: 7, scale: 2 }),
    filedAt: timestamp("filed_at", { withTimezone: true }),
    sourceUrl: text("source_url"),
  },
  (table) => [
    primaryKey({ columns: [table.symbol, table.quarterEnd] }),
  ],
);

export const announcements = pgTable(
  "announcements",
  {
    id: bigint("id", { mode: "number" }).generatedAlwaysAsIdentity().primaryKey(),
    symbol: text("symbol")
      .notNull()
      .references(() => stocks.symbol),
    exchangeRef: text("exchange_ref").notNull().unique(),
    announcedAt: timestamp("announced_at", { withTimezone: true }).notNull(),
    subject: text("subject").notNull(),
    title: text("title").notNull(),
    attachmentUrl: text("attachment_url"),
    importance: importance("importance"),
    aiSummary: text("ai_summary"),
    aiModel: text("ai_model"),
    aiPromptVersion: text("ai_prompt_version"),
    aiWrittenAt: timestamp("ai_written_at", { withTimezone: true }),
  },
  (table) => [
    index("announcements_symbol_announced_at_index").on(table.symbol, desc(table.announcedAt)),
    index("announcements_importance_announced_at_index")
      .on(table.importance, desc(table.announcedAt))
      .where(sql`${table.importance} in ('high', 'medium')`),
  ],
);

export const alerts = pgTable(
  "alerts",
  {
    id: bigint("id", { mode: "number" }).generatedAlwaysAsIdentity().primaryKey(),
    symbol: text("symbol")
      .notNull()
      .references(() => stocks.symbol),
    kind: alertKind("kind").notNull(),
    severity: severity("severity").notNull(),
    title: text("title").notNull(),
    detail: text("detail"),
    dedupeKey: text("dedupe_key").notNull().unique(),
    sourceTable: text("source_table"),
    sourceId: text("source_id"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("alerts_symbol_created_at_index").on(table.symbol, desc(table.createdAt)),
  ],
);

// ---------------------------------------------------------------------------
// App tables
// ---------------------------------------------------------------------------

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: citext("email").notNull().unique(),
  name: text("name"),
  role: text("role").notNull().default("user"),
  emailVerified: boolean("email_verified").notNull().default(false),
  image: text("image"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

// Better Auth's tables (ADR-0028), task 010. The 1.7.14 model fields, snake_case,
// in this repo's convention: camelCase property keys, snake_case columns. Ids are
// `uuid` with a `defaultRandom()` default so the rows Better Auth writes (which
// never carry an id with `advanced.database.generateId: "uuid"` + the Postgres
// adapter, which reports `supportsUUIDs`) get the database-generated uuid.
// `account.password` is the credential hash store — never `users`.
export const session = pgTable("session", {
  id: uuid("id").primaryKey().defaultRandom(),
  token: text("token").notNull().unique(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  ipAddress: text("ip_address"),
  userAgent: text("user_agent"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const account = pgTable(
  "account",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    accountId: text("account_id").notNull(),
    providerId: text("provider_id").notNull(),
    password: text("password"),
    accessToken: text("access_token"),
    refreshToken: text("refresh_token"),
    idToken: text("id_token"),
    accessTokenExpiresAt: timestamp("access_token_expires_at", { withTimezone: true }),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at", { withTimezone: true }),
    scope: text("scope"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [uniqueIndex("account_provider_id_account_id_unique").on(table.providerId, table.accountId)],
);

export const verification = pgTable("verification", {
  id: uuid("id").primaryKey().defaultRandom(),
  identifier: text("identifier").notNull(),
  value: text("value").notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

// Better Auth's database rate-limit store (`rateLimit.storage: "database"`).
// `last_request` holds `Date.now()` milliseconds as a bigint, never a timestamp.
export const rateLimit = pgTable("rate_limit", {
  id: uuid("id").primaryKey().defaultRandom(),
  key: text("key").notNull().unique(),
  count: integer("count").notNull(),
  lastRequest: bigint("last_request", { mode: "number" }).notNull(),
});

export const watchlistItems = pgTable(
  "watchlist_items",
  {
    userId: uuid("user_id").references(() => users.id, { onDelete: "cascade" }),
    symbol: text("symbol").references(() => stocks.symbol),
    addedAt: timestamp("added_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    primaryKey({ columns: [table.userId, table.symbol] }),
  ],
);

export const aiQuestions = pgTable(
  "ai_questions",
  {
    id: bigint("id", { mode: "number" }).generatedAlwaysAsIdentity().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    subjectType: text("subject_type").notNull(),
    subjectKey: text("subject_key").notNull(),
    question: text("question").notNull(),
    answer: text("answer").notNull(),
    model: text("model").notNull(),
    inputTokens: integer("input_tokens").notNull(),
    outputTokens: integer("output_tokens").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("ai_questions_user_id_created_at_index").on(table.userId, desc(table.createdAt)),
  ],
);

export const analysisJobs = pgTable(
  "analysis_jobs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    symbol: text("symbol")
      .notNull()
      .references(() => stocks.symbol),
    status: jobStatus("status").notNull(),
    reason: text("reason").notNull(),
    currentStep: text("current_step"),
    workerRunId: text("worker_run_id"),
    workerRunUrl: text("worker_run_url"),
    queuedAt: timestamp("queued_at", { withTimezone: true }).notNull().defaultNow(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
    lastEventAt: timestamp("last_event_at", { withTimezone: true }),
    error: text("error"),
  },
  (table) => [
    uniqueIndex("analysis_jobs_symbol_unique")
      .on(table.symbol)
      .where(sql`${table.status} in ('queued', 'running')`),
    index("analysis_jobs_status_queued_at_index").on(table.status, table.queuedAt),
  ],
);

export const analysisJobEvents = pgTable(
  "analysis_job_events",
  {
    id: bigint("id", { mode: "number" }).generatedAlwaysAsIdentity().primaryKey(),
    jobId: uuid("job_id")
      .notNull()
      .references(() => analysisJobs.id, { onDelete: "cascade" }),
    step: text("step").notNull(),
    state: text("state").notNull(),
    message: text("message"),
    at: timestamp("at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("analysis_job_events_job_id_at_index").on(table.jobId, table.at),
  ],
);

export const analysisRequests = pgTable(
  "analysis_requests",
  {
    id: bigint("id", { mode: "number" }).generatedAlwaysAsIdentity().primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    symbol: text("symbol")
      .notNull()
      .references(() => stocks.symbol),
    served: analysisServed("served").notNull(),
    jobId: uuid("job_id").references(() => analysisJobs.id),
    requestedAt: timestamp("requested_at", { withTimezone: true }).notNull().defaultNow(),
    charged: boolean("charged").notNull().default(true),
  },
  (table) => [
    index("analysis_requests_user_id_requested_at_index").on(table.userId, desc(table.requestedAt)),
  ],
);

export const settings = pgTable("settings", {
  key: text("key").primaryKey(),
  value: jsonb("value").notNull(),
  description: text("description").notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  updatedBy: uuid("updated_by").references(() => users.id),
});

export const imports = pgTable("imports", {
  commitSha: text("commit_sha").primaryKey(),
  startedAt: timestamp("started_at", { withTimezone: true }),
  finishedAt: timestamp("finished_at", { withTimezone: true }),
  status: text("status").notNull(),
  files: integer("files"),
  error: text("error"),
});

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

export const watchedSymbols = pgView("watched_symbols", {
  symbol: text("symbol").notNull(),
}).as(sql`select distinct ${watchlistItems.symbol} from ${watchlistItems}`);

// ---------------------------------------------------------------------------
// Relations for Better Auth's Drizzle adapter (task 010)
// ---------------------------------------------------------------------------
// Better Auth's adapter loads sessions and users with relational queries
// (db.query.*.findFirst({ with: ... })), so the joined tables need relations.
// The `with` keys it builds are the plural of the joined model — "users" for a
// session→user join, "accounts" for a user→account join — so the relation
// *names* follow that, even though each is a one-to-one/one-to-many over users.
// Nothing else in the app uses these relations.
export const userRelations = relations(users, ({ many }) => ({
  accounts: many(account),
}));

export const sessionRelations = relations(session, ({ one }) => ({
  users: one(users, { fields: [session.userId], references: [users.id] }),
}));

export const accountRelations = relations(account, ({ one }) => ({
  users: one(users, { fields: [account.userId], references: [users.id] }),
}));