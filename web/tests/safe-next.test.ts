import { describe, expect, it } from "vitest";
import { safeNextPath } from "@/lib/safe-next";

const ORIGIN = "https://app.example.com";

describe("safeNextPath (code review round 1 finding 3)", () => {
  it("accepts a plain same-site path, keeping its query and hash", () => {
    expect(safeNextPath("/admin/invite", ORIGIN)).toBe("/admin/invite");
    expect(safeNextPath("/admin/invite?from=1#top", ORIGIN)).toBe("/admin/invite?from=1#top");
  });

  it("accepts the root", () => {
    expect(safeNextPath("/", ORIGIN)).toBe("/");
  });

  it("falls back for a protocol-relative URL", () => {
    expect(safeNextPath("//evil.example/x", ORIGIN)).toBe("/");
  });

  it("falls back for a backslash URL (browsers treat \\ as /)", () => {
    expect(safeNextPath("/\\evil.example/x", ORIGIN)).toBe("/");
  });

  it("falls back for an absolute URL", () => {
    expect(safeNextPath("https://evil.example/x", ORIGIN)).toBe("/");
  });

  it("falls back when next is absent or not a path", () => {
    expect(safeNextPath(null, ORIGIN)).toBe("/");
    expect(safeNextPath("", ORIGIN)).toBe("/");
    expect(safeNextPath("admin/invite", ORIGIN)).toBe("/");
  });
});