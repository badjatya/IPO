import { basename } from "node:path";

// The file classifier: which repo paths map to research tables (docs/db.md
// § Where the data comes from). Everything the routine also writes that the
// import does not own — `data/latest.*`, the rendered email (`.html`, `.txt`),
// `analysis/rhp/<key>.txt`, later `data/stocks/*` files — returns "not
// research" and is ignored.

export type ResearchKind = "snapshot" | "card" | "analysis" | "report" | "outcome";

const SNAPSHOT_RE = /^data\/snapshots\/[^/]+\.json$/;
const CARD_RE = /^analysis\/[^/]+\.json$/;
const ANALYSIS_RE = /^analysis\/[^/]+\.md$/;
const REPORT_RE = /^reports\/[^/]+-(?:am|pm)\.json$/;
const OUTCOMES_PATH = "data/outcomes.json";

/** The research kind a repo path maps to, or null for non-research files. */
export function classifyResearchFile(path: string): ResearchKind | null {
  if (path === OUTCOMES_PATH) return "outcome";
  if (SNAPSHOT_RE.test(path)) return "snapshot";
  if (CARD_RE.test(path)) return "card";
  if (ANALYSIS_RE.test(path)) return "analysis";
  if (REPORT_RE.test(path)) return "report";
  return null;
}

/** `analysis/zetwerk.json` → `zetwerk`; `analysis/rhp/x.txt` → null. */
export function researchKey(path: string): string | null {
  if (classifyResearchFile(path) !== "card" && classifyResearchFile(path) !== "analysis") return null;
  const base = basename(path);
  const dot = base.lastIndexOf(".");
  return dot === -1 ? base : base.slice(0, dot);
}