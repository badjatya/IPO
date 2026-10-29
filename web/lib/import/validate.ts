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

/** A number field: null/undefined pass through, anything numeric stays verbatim. */
export function maybeNumber(value: unknown, label: string): number | string | undefined {
  if (value === null || value === undefined) return undefined;
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) return value;
  throw new Error(`invalid ${label}: ${JSON.stringify(value)} (expected a number)`);
}