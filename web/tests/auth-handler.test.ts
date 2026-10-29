import { describe, expect, it, vi } from "vitest";

// Importing the handler module evaluates lib/auth, which builds the adapter
// over db() — a non-empty DATABASE_URL satisfies parseEnv, no connection opens.
vi.stubEnv("DATABASE_URL", "postgresql://test@localhost:5432/test");

describe("/api/auth/[...all] route", () => {
  it("exports clean GET and POST handlers", async () => {
    const route = await import("@/app/api/auth/[...all]/route");
    expect(typeof route.GET).toBe("function");
    expect(typeof route.POST).toBe("function");
  });
});