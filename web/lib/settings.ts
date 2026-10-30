// The app's list of known settings keys and their types (db.md § settings).
// Quotas and caps themselves live in the `settings` table and never here
// (AGENTS.md rule 6): this module is only the type metadata the page and every
// write path share — which keys exist and the smallest whole number each
// accepts. New settings are added as new rows plus an entry in this list
// (db.md); descriptions stay in the table, never in code.
export interface SettingSpec {
  /** The smallest whole number the key accepts. */
  min: number;
}

export const KNOWN_SETTINGS: Readonly<Record<string, SettingSpec>> = {
  ask_daily_limit_per_user: { min: 0 },
  analysis_monthly_limit_per_user: { min: 0 },
  analysis_daily_limit_platform: { min: 0 },
  analysis_refresh_after_days: { min: 1 },
};

export type ValidSetting = { ok: true; key: string; value: number };
export type InvalidSetting = { ok: false; error: string };

/**
 * The one pure validator every settings write path uses. The value must be a
 * JSON number — the string "5", a fraction, a boolean, null or an object are
 * refused, and there is no silent coercion — that is a whole number at or
 * above the key's bound. Returns the parsed key and number, or one concrete
 * error message per failure.
 */
export function validateSettingValue(body: unknown): ValidSetting | InvalidSetting {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return { ok: false, error: "body must be an object with key and value" };
  }
  const { key, value } = body as { key?: unknown; value?: unknown };
  // Own properties only: "constructor" must not pass as a key.
  if (typeof key !== "string" || !Object.hasOwn(KNOWN_SETTINGS, key)) {
    return { ok: false, error: "unknown settings key" };
  }
  if (typeof value !== "number") {
    return { ok: false, error: "value must be a number" };
  }
  if (!Number.isInteger(value)) {
    return { ok: false, error: "value must be a whole number" };
  }
  const min = KNOWN_SETTINGS[key].min;
  if (value < min) {
    return { ok: false, error: `value must be at least ${min}` };
  }
  return { ok: true, key, value };
}