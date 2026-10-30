import { createHash } from "node:crypto";
import { ipoAnalyses } from "@/db/schema";

// Maps `analysis/<key>.md` (the full deep analysis) to one `ipo_analyses` row,
// replaced on the natural key. `content_sha` is the sha256 of the markdown, so
// an unchanged analysis is never rewritten. The `ai_*` provenance columns stay
// null: the markdown has no provenance marker until tasks 020/021 define one
// (docs/db.md § Import and rebuild). The RHP text itself stays in git, and
// `rhp_text_path` names it.

export type NewAnalysis = typeof ipoAnalyses.$inferInsert;

export function parseAnalysisDocument(markdown: string, key: string): NewAnalysis {
  return {
    ipoKey: key,
    markdown,
    rhpTextPath: `analysis/rhp/${key}.txt`,
    contentSha: createHash("sha256").update(markdown).digest("hex"),
  };
}