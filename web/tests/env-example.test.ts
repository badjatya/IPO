import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const read = (path: string) => readFileSync(fileURLToPath(new URL(path, import.meta.url)), "utf8");

// `NAME=value` lines; comments and blank lines skipped.
const entries = read("../.env.example")
  .split("\n")
  .filter((line) => line.trim() && !line.startsWith("#"))
  .map((line) => line.split("=", 2) as [string, string]);

// Rows of tech.md § Configuration and secrets whose "Used by" column names the app.
const appVariables = read("../../docs/tech.md")
  .split("\n")
  .map((line) => line.match(/^\| `([A-Z_]+)` \| ([^|]+) \|/))
  .filter((match) => match !== null && /\bApp\b/.test(match[2]))
  .map((match) => match![1]);

describe(".env.example", () => {
  it("lists exactly the app's variables from tech.md", () => {
    expect(appVariables.length).toBeGreaterThan(0);
    expect(entries.map(([name]) => name).toSorted()).toEqual(appVariables.toSorted());
  });

  it("holds no values, so no secret lands in git", () => {
    const values = Object.fromEntries(entries);
    const empty = Object.fromEntries(entries.map(([name]) => [name, ""]));
    expect(values).toEqual(empty);
  });
});
