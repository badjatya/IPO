CREATE TYPE "public"."alert_kind" AS ENUM('results', 'announcement', 'pledge_up', 'promoter_down', 'fii_move', 'dii_move');--> statement-breakpoint
CREATE TYPE "public"."analysis_served" AS ENUM('saved', 'new', 'refresh');--> statement-breakpoint
CREATE TYPE "public"."anchor_grade" AS ENUM('strong', 'average', 'weak', 'pending');--> statement-breakpoint
CREATE TYPE "public"."card_source" AS ENUM('rhp', 'web');--> statement-breakpoint
CREATE TYPE "public"."importance" AS ENUM('high', 'medium', 'low', 'routine');--> statement-breakpoint
CREATE TYPE "public"."ipo_phase" AS ENUM('announced', 'upcoming', 'open', 'closing_today', 'awaiting_listing', 'listing_today', 'listed');--> statement-breakpoint
CREATE TYPE "public"."job_status" AS ENUM('queued', 'running', 'done', 'failed');--> statement-breakpoint
CREATE TYPE "public"."report_session" AS ENUM('AM', 'PM');--> statement-breakpoint
CREATE TYPE "public"."rhp_source" AS ENUM('nse', 'sebi');--> statement-breakpoint
CREATE TYPE "public"."severity" AS ENUM('info', 'watch', 'warning');--> statement-breakpoint
CREATE TYPE "public"."sub_category" AS ENUM('qib', 'nii', 'snii', 'bnii', 'retail', 'employee', 'total');--> statement-breakpoint
CREATE TYPE "public"."verdict" AS ENUM('apply', 'listing_gains', 'neutral', 'avoid', 'pending');--> statement-breakpoint
CREATE TABLE "ai_questions" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "ai_questions_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"user_id" uuid NOT NULL,
	"subject_type" text NOT NULL,
	"subject_key" text NOT NULL,
	"question" text NOT NULL,
	"answer" text NOT NULL,
	"model" text NOT NULL,
	"input_tokens" integer NOT NULL,
	"output_tokens" integer NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "alerts" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "alerts_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"symbol" text NOT NULL,
	"kind" "alert_kind" NOT NULL,
	"severity" "severity" NOT NULL,
	"title" text NOT NULL,
	"detail" text,
	"dedupe_key" text NOT NULL,
	"source_table" text,
	"source_id" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "alerts_dedupe_key_unique" UNIQUE("dedupe_key")
);
--> statement-breakpoint
CREATE TABLE "analysis_job_events" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "analysis_job_events_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"job_id" uuid NOT NULL,
	"step" text NOT NULL,
	"state" text NOT NULL,
	"message" text,
	"at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "analysis_jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"symbol" text NOT NULL,
	"status" "job_status" NOT NULL,
	"reason" text NOT NULL,
	"current_step" text,
	"worker_run_id" text,
	"worker_run_url" text,
	"queued_at" timestamp with time zone DEFAULT now() NOT NULL,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"last_event_at" timestamp with time zone,
	"error" text
);
--> statement-breakpoint
CREATE TABLE "analysis_requests" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "analysis_requests_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"user_id" uuid NOT NULL,
	"symbol" text NOT NULL,
	"served" "analysis_served" NOT NULL,
	"job_id" uuid,
	"requested_at" timestamp with time zone DEFAULT now() NOT NULL,
	"charged" boolean DEFAULT true NOT NULL
);
--> statement-breakpoint
CREATE TABLE "announcements" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "announcements_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"symbol" text NOT NULL,
	"exchange_ref" text NOT NULL,
	"announced_at" timestamp with time zone NOT NULL,
	"subject" text NOT NULL,
	"title" text NOT NULL,
	"attachment_url" text,
	"importance" "importance",
	"ai_summary" text,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	CONSTRAINT "announcements_exchange_ref_unique" UNIQUE("exchange_ref")
);
--> statement-breakpoint
CREATE TABLE "imports" (
	"commit_sha" text PRIMARY KEY NOT NULL,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"status" text NOT NULL,
	"files" integer,
	"error" text
);
--> statement-breakpoint
CREATE TABLE "ipo_analyses" (
	"ipo_key" text PRIMARY KEY NOT NULL,
	"markdown" text NOT NULL,
	"rhp_text_path" text,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	"content_sha" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ipo_cards" (
	"ipo_key" text PRIMARY KEY NOT NULL,
	"source" "card_source" NOT NULL,
	"analysed_on" date,
	"verdict" "verdict" NOT NULL,
	"verdict_text" text NOT NULL,
	"summary" text,
	"financials" text,
	"quota" text,
	"positives" text[] DEFAULT '{}' NOT NULL,
	"red_flags" text[] DEFAULT '{}' NOT NULL,
	"anchor" text,
	"anchor_grade" "anchor_grade" NOT NULL,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	"source_file" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ipo_outcomes" (
	"ipo_key" text PRIMARY KEY NOT NULL,
	"symbol" text NOT NULL,
	"listing_date" date NOT NULL,
	"issue_price" numeric(12, 2) NOT NULL,
	"listing_price" numeric(12, 2) NOT NULL,
	"day_close" numeric(12, 2),
	"day_high" numeric(12, 2),
	"day_low" numeric(12, 2),
	"listing_gain_pct" numeric(7, 2),
	"close_gain_pct" numeric(7, 2),
	"gmp_eve" numeric(12, 2),
	"gmp_eve_pct" numeric(7, 2),
	"gmp_eve_snapshot" timestamp with time zone,
	"gmp_miss_pts" numeric(7, 2),
	"verdict" "verdict",
	"verdict_text" text,
	"best_category" text,
	"verdict_report" text,
	"anchor_grade" "anchor_grade",
	"pe" numeric(10, 2),
	"size_cr" numeric(14, 2),
	"sub_qib" numeric(10, 2),
	"sub_snii" numeric(10, 2),
	"sub_bnii" numeric(10, 2),
	"sub_retail" numeric(10, 2),
	"sub_total" numeric(10, 2),
	"subscription_source" text,
	"price_source" text,
	"recorded_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ipo_snapshots" (
	"ipo_key" text,
	"taken_at" timestamp with time zone,
	"phase" "ipo_phase" NOT NULL,
	"gmp" numeric(12, 2),
	"gmp_low" numeric(12, 2),
	"gmp_high" numeric(12, 2),
	"gmp_pct" numeric(7, 2),
	"gmp_updated" text,
	"pe" numeric(10, 2),
	"allotment" jsonb,
	"source_file" text NOT NULL,
	CONSTRAINT "ipo_snapshots_ipo_key_taken_at_pk" PRIMARY KEY("ipo_key","taken_at")
);
--> statement-breakpoint
CREATE TABLE "ipo_subscriptions" (
	"ipo_key" text,
	"taken_at" timestamp with time zone,
	"category" "sub_category",
	"shares_offered" bigint,
	"shares_bid" bigint,
	"times" numeric(10, 2),
	CONSTRAINT "ipo_subscriptions_ipo_key_taken_at_category_pk" PRIMARY KEY("ipo_key","taken_at","category")
);
--> statement-breakpoint
CREATE TABLE "ipo_verdicts" (
	"report_date" date,
	"session" "report_session",
	"ipo_key" text,
	"verdict" "verdict",
	"verdict_text" text,
	"best_category" text,
	"category_note" text,
	"overrides" jsonb,
	CONSTRAINT "ipo_verdicts_report_date_session_ipo_key_pk" PRIMARY KEY("report_date","session","ipo_key")
);
--> statement-breakpoint
CREATE TABLE "ipos" (
	"key" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"symbol" text,
	"open_date" date,
	"close_date" date,
	"allotment_date" date,
	"listing_date" date,
	"price_low" numeric(12, 2),
	"price_high" numeric(12, 2),
	"lot_size" integer,
	"issue_size_cr" numeric(14, 2),
	"issue_size_text" text,
	"face_value" text,
	"lead_managers" text,
	"registrar" text,
	"rhp_url" text,
	"rhp_source" "rhp_source",
	"investorgain_url" text,
	"phase" "ipo_phase" NOT NULL,
	"anchor_done" boolean DEFAULT false NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "quarterly_results" (
	"symbol" text,
	"period_end" date,
	"consolidated" boolean,
	"revenue_cr" numeric(14, 2),
	"other_income_cr" numeric(14, 2),
	"expenses_cr" numeric(14, 2),
	"ebitda_cr" numeric(14, 2),
	"pat_cr" numeric(14, 2),
	"eps" numeric(10, 2),
	"filed_at" timestamp with time zone,
	"source_url" text,
	"ai_summary" text,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	CONSTRAINT "quarterly_results_symbol_period_end_consolidated_pk" PRIMARY KEY("symbol","period_end","consolidated")
);
--> statement-breakpoint
CREATE TABLE "reports" (
	"report_date" date,
	"session" "report_session",
	"headline" text,
	"notes" text[] DEFAULT '{}' NOT NULL,
	"quiet" boolean NOT NULL,
	"carried_from" text,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	"commit_sha" text,
	"source_file" text NOT NULL,
	CONSTRAINT "reports_report_date_session_pk" PRIMARY KEY("report_date","session")
);
--> statement-breakpoint
CREATE TABLE "settings" (
	"key" text PRIMARY KEY NOT NULL,
	"value" jsonb NOT NULL,
	"description" text NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_by" uuid
);
--> statement-breakpoint
CREATE TABLE "shareholding" (
	"symbol" text,
	"quarter_end" date,
	"promoter_pct" numeric(7, 2),
	"fii_pct" numeric(7, 2),
	"dii_pct" numeric(7, 2),
	"public_pct" numeric(7, 2),
	"other_pct" numeric(7, 2),
	"promoter_pledged_pct" numeric(7, 2),
	"filed_at" timestamp with time zone,
	"source_url" text,
	CONSTRAINT "shareholding_symbol_quarter_end_pk" PRIMARY KEY("symbol","quarter_end")
);
--> statement-breakpoint
CREATE TABLE "stock_analyses" (
	"symbol" text PRIMARY KEY NOT NULL,
	"summary" text NOT NULL,
	"financials" text,
	"valuation" text,
	"positives" text[] DEFAULT '{}' NOT NULL,
	"red_flags" text[] DEFAULT '{}' NOT NULL,
	"markdown" text NOT NULL,
	"analysed_on" date NOT NULL,
	"based_on_period" date,
	"ai_model" text,
	"ai_prompt_version" text,
	"ai_written_at" timestamp with time zone,
	"source_file" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "stock_quotes" (
	"symbol" text PRIMARY KEY NOT NULL,
	"price" numeric(12, 2),
	"change_pct" numeric(7, 2),
	"week52_high" numeric(12, 2),
	"week52_low" numeric(12, 2),
	"market_cap_cr" numeric(14, 2),
	"pe" numeric(10, 2),
	"as_of" timestamp with time zone NOT NULL
);
--> statement-breakpoint
CREATE TABLE "stocks" (
	"symbol" text PRIMARY KEY NOT NULL,
	"isin" text,
	"name" text NOT NULL,
	"industry" text,
	"ipo_key" text,
	"active" boolean NOT NULL,
	"last_researched_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" "citext" NOT NULL,
	"name" text,
	"role" text DEFAULT 'user' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "watchlist_items" (
	"user_id" uuid,
	"symbol" text,
	"added_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "watchlist_items_user_id_symbol_pk" PRIMARY KEY("user_id","symbol")
);
--> statement-breakpoint
ALTER TABLE "ai_questions" ADD CONSTRAINT "ai_questions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "alerts" ADD CONSTRAINT "alerts_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "analysis_job_events" ADD CONSTRAINT "analysis_job_events_job_id_analysis_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."analysis_jobs"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "analysis_jobs" ADD CONSTRAINT "analysis_jobs_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "analysis_requests" ADD CONSTRAINT "analysis_requests_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "analysis_requests" ADD CONSTRAINT "analysis_requests_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "analysis_requests" ADD CONSTRAINT "analysis_requests_job_id_analysis_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."analysis_jobs"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "announcements" ADD CONSTRAINT "announcements_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_analyses" ADD CONSTRAINT "ipo_analyses_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_cards" ADD CONSTRAINT "ipo_cards_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_outcomes" ADD CONSTRAINT "ipo_outcomes_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_snapshots" ADD CONSTRAINT "ipo_snapshots_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_subscriptions" ADD CONSTRAINT "ipo_subscriptions_ipo_key_taken_at_ipo_snapshots_ipo_key_taken_at_fk" FOREIGN KEY ("ipo_key","taken_at") REFERENCES "public"."ipo_snapshots"("ipo_key","taken_at") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_verdicts" ADD CONSTRAINT "ipo_verdicts_report_date_session_reports_report_date_session_fk" FOREIGN KEY ("report_date","session") REFERENCES "public"."reports"("report_date","session") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ipo_verdicts" ADD CONSTRAINT "ipo_verdicts_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "quarterly_results" ADD CONSTRAINT "quarterly_results_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "settings" ADD CONSTRAINT "settings_updated_by_users_id_fk" FOREIGN KEY ("updated_by") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "shareholding" ADD CONSTRAINT "shareholding_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "stock_analyses" ADD CONSTRAINT "stock_analyses_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "stock_quotes" ADD CONSTRAINT "stock_quotes_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "stocks" ADD CONSTRAINT "stocks_ipo_key_ipos_key_fk" FOREIGN KEY ("ipo_key") REFERENCES "public"."ipos"("key") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "watchlist_items" ADD CONSTRAINT "watchlist_items_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "watchlist_items" ADD CONSTRAINT "watchlist_items_symbol_stocks_symbol_fk" FOREIGN KEY ("symbol") REFERENCES "public"."stocks"("symbol") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "ai_questions_user_id_created_at_index" ON "ai_questions" USING btree ("user_id","created_at" desc);--> statement-breakpoint
CREATE INDEX "alerts_symbol_created_at_index" ON "alerts" USING btree ("symbol","created_at" desc);--> statement-breakpoint
CREATE INDEX "analysis_job_events_job_id_at_index" ON "analysis_job_events" USING btree ("job_id","at");--> statement-breakpoint
CREATE UNIQUE INDEX "analysis_jobs_symbol_unique" ON "analysis_jobs" USING btree ("symbol") WHERE "analysis_jobs"."status" in ('queued', 'running');--> statement-breakpoint
CREATE INDEX "analysis_jobs_status_queued_at_index" ON "analysis_jobs" USING btree ("status","queued_at");--> statement-breakpoint
CREATE INDEX "analysis_requests_user_id_requested_at_index" ON "analysis_requests" USING btree ("user_id","requested_at" desc);--> statement-breakpoint
CREATE INDEX "announcements_symbol_announced_at_index" ON "announcements" USING btree ("symbol","announced_at" desc);--> statement-breakpoint
CREATE INDEX "announcements_importance_announced_at_index" ON "announcements" USING btree ("importance","announced_at" desc) WHERE "announcements"."importance" in ('high', 'medium');--> statement-breakpoint
CREATE INDEX "ipo_snapshots_taken_at_index" ON "ipo_snapshots" USING btree ("ipo_key","taken_at" desc);--> statement-breakpoint
CREATE INDEX "ipo_verdicts_ipo_key_report_date_index" ON "ipo_verdicts" USING btree ("ipo_key","report_date" desc,"session" desc);--> statement-breakpoint
CREATE INDEX "ipos_phase_index" ON "ipos" USING btree ("phase");--> statement-breakpoint
CREATE INDEX "ipos_listing_date_index" ON "ipos" USING btree ("listing_date");--> statement-breakpoint
CREATE UNIQUE INDEX "ipos_symbol_unique" ON "ipos" USING btree ("symbol") WHERE "ipos"."symbol" is not null;--> statement-breakpoint
CREATE INDEX "quarterly_results_symbol_period_end_index" ON "quarterly_results" USING btree ("symbol","period_end" desc);--> statement-breakpoint
CREATE UNIQUE INDEX "stocks_isin_unique" ON "stocks" USING btree ("isin") WHERE "stocks"."isin" is not null;--> statement-breakpoint
CREATE VIEW "public"."watched_symbols" AS (select distinct "watchlist_items"."symbol" from "watchlist_items");