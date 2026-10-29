import { describe, expect, it } from "vitest";
import {
  buildPooledUri,
  buildUriFromParts,
  expiryStamp,
  findDefaultBranch,
  isProtectedBranch,
} from "../scripts/neon-branch.mjs";

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

// The Neon API v2 Branch object's documented shape (GET /projects/{id}/branches).
function branchFixture(overrides = {}) {
  return {
    id: "br-spring-water-12345678",
    project_id: "project-123",
    parent_id: null,
    parent_lsn: "0/0",
    name: "main",
    current_state: "ready",
    pending_state: null,
    creation_source: "console",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    default: false,
    physical_size: 0,
    logical_size: 0,
    data_size_snapshot_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

describe("findDefaultBranch", () => {
  it("picks the branch marked `default: true`", () => {
    const branches = [
      branchFixture({ id: "br-feature-1", name: "feature" }),
      branchFixture({ id: "br-main-1", name: "main", default: true }),
    ];
    expect(findDefaultBranch(branches)?.id).toBe("br-main-1");
  });

  it("returns undefined when no branch carries `default: true`", () => {
    expect(findDefaultBranch([branchFixture(), branchFixture({ id: "br-2" })])).toBeUndefined();
  });

  it("does not match the old `is_default` spelling, which the API never sends", () => {
    const branches = [branchFixture({ id: "br-old", name: "main", is_default: true })];
    expect(findDefaultBranch(branches)).toBeUndefined();
  });

  it("returns undefined for an empty or missing list", () => {
    expect(findDefaultBranch([])).toBeUndefined();
    expect(findDefaultBranch(undefined)).toBeUndefined();
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