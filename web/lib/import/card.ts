import { anchorGrade, cardSource, ipoCards, verdict } from "@/db/schema";
import { checkEnum, maybeDate, maybeString } from "./validate";

// Maps `analysis/<key>.json` (the cached facts card) to one `ipo_cards` row,
// replaced on the natural key (ipo_key). The `ai_model` / `ai_prompt_version` /
// `ai_written_at` fields are copied when the file carries them (task 004);
// legacy cards import with nulls. `ai_written_at` is a timestamptz, so it is
// converted to a `Date` (see types.ts). docs/db.md § Where the data comes from.

export type NewCard = typeof ipoCards.$inferInsert;

export function parseCardDocument(json: unknown, key: string, sourceFile: string): NewCard {
  if (typeof json !== "object" || json === null) {
    throw new Error(`${sourceFile}: not a JSON object`);
  }
  const card = json as Record<string, unknown>;

  const row: Partial<NewCard> = {
    ipoKey: key,
    sourceFile,
    positives: [],
    redFlags: [],
  };
  const set = <K extends keyof NewCard>(column: K, value: NewCard[K] | null | undefined) => {
    if (value !== null && value !== undefined) row[column] = value;
  };

  set("source", checkEnum(cardSource.enumValues, card.source, `${key}.source`));
  set("analysedOn", maybeString(card.analysed));
  set("verdict", checkEnum(verdict.enumValues, card.verdict, `${key}.verdict`));
  set("verdictText", maybeString(card.verdict_text));
  set("summary", maybeString(card.summary));
  set("financials", maybeString(card.financials));
  set("quota", maybeString(card.quota));
  if (Array.isArray(card.positives)) row.positives = card.positives as string[];
  if (Array.isArray(card.red_flags)) row.redFlags = card.red_flags as string[];
  set("anchor", maybeString(card.anchor));
  set("anchorGrade", checkEnum(anchorGrade.enumValues, card.anchor_grade, `${key}.anchor_grade`));

  set("aiModel", maybeString(card.ai_model));
  set("aiPromptVersion", maybeString(card.ai_prompt_version));
  set("aiWrittenAt", maybeDate(card.ai_written_at, `${key}.ai_written_at`));

  // Missing fields stay absent, so `replacedSet` can null them in the update;
  // the required columns (`source`, `verdict`, `verdict_text`, `anchor_grade`)
  // are guaranteed by the file — the cast states the row is complete for the
  // insert, which rejects a card lacking them with a not-null violation.
  return row as NewCard;
}