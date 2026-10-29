import { describe, expect, it } from "vitest";
import { buildPooledUri, buildUriFromParts, expiryStamp, isProtectedBranch } from "../scripts/neon-branch.mjs";

const unpooled = "postgresql://neondb_owner:secret@ep-abc-123.us-east-2.aws.neon.tech/neondb?sslmode=require";

describe("buildPooledUri", () => {
  it("inserts -pooler before the region (ep-… → ep-…-pooler)", () => {
    const pooled = new URL(buildPooledUri(unpooled));
    expect(pooled.hostname).toBe("ep-abc-123-pooler.us-east-2.aws.neon.tech");
    expect(pooled.username).toBe("neondb_owner");
    expect(pooled.pathname).toBe("/neondb");
  });

  it("leaves an already-pooled host alone", () => {
    const pooled = "postgresql://neondb_owner:secret@ep-abc-123-pooler.us-east-2.aws.neon.tech/neondb";
    expect(buildPooledUri(pooled)).toBe(pooled);
  });

  it("throws on a host with no region dot", () => {
    expect(() => buildPooledUri("postgresql://u:p@localhost/neondb")).toThrow(/pooled URI/);
  });
});

describe("isProtectedBranch", () => {
  it("protects the default branch by id", () => {
    expect(isProtectedBranch({ id: "br-default", name: "production" }, { defaultBranchId: "br-default" })).toBe(
      true,
    );
  });

  it("protects dev by name, case-insensitively", () => {
    expect(isProtectedBranch({ id: "br-1", name: "dev" }, {})).toBe(true);
    expect(isProtectedBranch({ id: "br-1", name: "DEV" }, {})).toBe(true);
  });

  it("protects the default branch by name too", () => {
    expect(
      isProtectedBranch({ id: "br-x", name: "production" }, { defaultBranchName: "production" }),
    ).toBe(true);
  });

  it("does not protect a throwaway branch", () => {
    expect(
      isProtectedBranch(
        { id: "br-db-test-1", name: "db-test-1793299000000" },
        { defaultBranchId: "br-default", defaultBranchName: "production" },
      ),
    ).toBe(false);
    expect(isProtectedBranch(undefined, { defaultBranchId: "br-default" })).toBe(false);
  });
});

describe("expiryStamp", () => {
  it("is an ISO timestamp one day ahead of the given now", () => {
    const now = new Date("2026-10-29T10:00:00Z");
    expect(new Date(expiryStamp(now)).toISOString()).toBe("2026-10-30T10:00:00.000Z");
  });
});

describe("buildUriFromParts", () => {
  it("builds a URI from the create-branch parts", () => {
    expect(
      buildUriFromParts({
        endpointHost: "ep-abc-123.us-east-2.aws.neon.tech",
        roleName: "neondb_owner",
        rolePassword: "secret",
        databaseName: "neondb",
      }),
    ).toBe(
      "postgresql://neondb_owner:secret@ep-abc-123.us-east-2.aws.neon.tech/neondb?sslmode=require",
    );
  });

  it("throws when a part is missing", () => {
    expect(() =>
      buildUriFromParts({ endpointHost: "ep-x", roleName: "r", rolePassword: "", databaseName: "n" }),
    ).toThrow(/cannot build/);
  });
});