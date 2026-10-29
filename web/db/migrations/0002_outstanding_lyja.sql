-- Decided seed rows for the settings table (values settled by the human;
-- docs/db.md § settings). analysis_daily_limit_platform deliberately has no
-- row until D08 sets a number (decided 2026-10-29): the app treats the missing
-- row as "gate closed" — no new or refreshed analysis is dispatched.
INSERT INTO "settings" ("key", "value", "description", "updated_at", "updated_by") VALUES
  ('ask_daily_limit_per_user', '5'::jsonb, 'How many Ask questions each person can send per day (resets at midnight IST). 0 turns Ask off for users. Applies to every account, including admins', now(), NULL),
  ('analysis_monthly_limit_per_user', '3'::jsonb, 'How many stock analyses each person can request per calendar month (IST). Every request counts, including one served from a saved analysis', now(), NULL),
  ('analysis_refresh_after_days', '30'::jsonb, 'A saved analysis older than this, or older than the company''s latest quarterly result, is refreshed before it''s served', now(), NULL);