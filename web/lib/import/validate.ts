// Shared validation for the import parsers. Enum-valued columns are checked
// against the schema's own enum arrays before insert; a value outside the enum,
// or a malformed file, throws and fails the commit's transaction (docs/db.md
// § Import and rebuild: "Any failure rolls back that commit's changes, and the
// next push retries"). Missing fields map to null — "not found", never an
// estimate (AGENTS.md rule 1).

/**
 * Validates `value` against an enum's values. Null/undefined pass through
 * (missing maps to null); anything else must be one of `values` or the parser
 * throws a message that lands in `imports.error`.
 */
export function checkEnum<T extends string>(values: readonly T[], value: unknown, label: string): T | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new Error(`invalid ${label}: ${JSON.stringify(value)} (expected one of ${values.join(", ")})`);
  }
  return value as T;
}

/** A string field: null/undefined pass through, everything else is strung. */
export function maybeString(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  return String(value);
}

/**
 * A `numeric` column value: null/undefined pass through; a JSON number or a
 * numeric string becomes a string, which is what Drizzle's `numeric` type
 * (mode "string") and the `numeric(...)` schema columns take.
 */
export function maybeDecimal(value: unknown, label: string): string | undefined {
  if (value === null || value === undefined) return undefined;
  if (typeof value === "number" && !Number.isNaN(value)) return String(value);
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) return value;
  throw new Error(`invalid ${label}: ${JSON.stringify(value)} (expected a number)`);
}

/**
 * An `integer` / `bigint` (mode "number") column value: null/undefined pass
 * through; a JSON number stays a number, a numeric string is converted.
 */
export function maybeInt(value: unknown, label: string): number | undefined {
  if (value === null || value === undefined) return undefined;
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) return Number(value);
  throw new Error(`invalid ${label}: ${JSON.stringify(value)} (expected a number)`);
}

/**
 * A timestamptz/timestamp column value: null/undefined pass through; anything
 * else becomes a `Date`. Drizzle's `timestamp()` columns are in date mode, so
 * the driver value must be a `Date` (`PgTimestamp.mapToDriverValue` calls
 * `toISOString()`); an unparseable value throws — the commit's transaction
 * rolls back and the error lands in `imports.error`.
 */
export function maybeDate(value: unknown, label: string): Date | undefined {
  if (value === null || value === undefined) return undefined;
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    throw new Error(`invalid ${label}: ${JSON.stringify(value)} (expected a date-time)`);
  }
  return date;
}