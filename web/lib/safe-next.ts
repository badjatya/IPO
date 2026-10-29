/**
 * The only `next` value the app accepts after a sign-in: a same-site path.
 * Protocol-relative ("//evil.example"), backslash ("/\evil.example", which
 * some browsers treat as a host separator) and absolute URLs all fall back to
 * "/", so a phishing link can never navigate a freshly signed-in user off the
 * site (code review round 1 finding 3).
 */
export function safeNextPath(next: string | null, origin: string): string {
  if (!next || !next.startsWith("/")) return "/";
  if (next.length > 1 && (next[1] === "/" || next[1] === "\\")) return "/";
  try {
    const resolved = new URL(next, origin);
    if (resolved.origin !== origin) return "/";
    return resolved.pathname + resolved.search + resolved.hash;
  } catch {
    return "/";
  }
}