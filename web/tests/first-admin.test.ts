import { afterEach, describe, expect, it, vi } from "vitest";
import { buildUpsertSql, parseArgs, runUpsert } from "../scripts/first-admin.mjs";

describe("parseArgs", () => {
  it("lowercases and trims the email, joins the rest as the name", () => {
    expect(parseArgs(["Alice@Example.com", "Alice", "Tester"])).toEqual({
      email: "alice@example.com",
      name: "Alice Tester",
    });
  });

  it("returns an empty email and no name without arguments", () => {
    expect(parseArgs([])).toEqual({ email: "", name: null });
  });
});

describe("buildUpsertSql", () => {
  it("inserts role admin and promotes on conflict, without touching name", () => {
    const { text, values } = buildUpsertSql("alice@example.com", null);
    expect(values).toEqual(["alice@example.com", "admin"]);
    expect(text).toContain("insert into users (email, role) values ($1, $2)");
    expect(text).toContain("on conflict (email) do update set role = excluded.role");
    expect(text).toContain("returning id, email, role");
    expect(text).not.toContain("name");
  });

  it("writes the name only when one is given", () => {
    const { text, values } = buildUpsertSql("bob@example.com", "Bob Builder");
    expect(values).toEqual(["bob@example.com", "Bob Builder", "admin"]);
    expect(text).toContain("insert into users (email, name, role) values ($1, $2, $3)");
    expect(text).toContain("role = excluded.role, name = excluded.name");
  });
});

describe("runUpsert (code review round 1 finding 1)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls the client with the parameterised two-arg shape sql.query(text, values)", async () => {
    const client = {
      query: vi.fn<
        (text: string, values: unknown[]) => Promise<{ id: string; email: string; role: string }[]>
      >(async () => [{ id: "u-1", email: "alice@example.com", role: "admin" }]),
    };
    const row = await runUpsert(client, "alice@example.com", null);
    expect(row).toMatchObject({ id: "u-1", role: "admin" });
    const { text, values } = buildUpsertSql("alice@example.com", null);
    expect(client.query).toHaveBeenCalledTimes(1);
    expect(client.query).toHaveBeenCalledWith(text, values);
  });

  it("returns null when the upsert returns no rows", async () => {
    const client = { query: vi.fn<(text: string, values: unknown[]) => Promise<unknown[]>>(async () => []) };
    await expect(runUpsert(client, "bob@example.com", null)).resolves.toBeNull();
  });
});