import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const requireAdminMock = vi.hoisted(() =>
  vi.fn<() => Promise<{ id: string; role: string }>>(async () => ({ id: "u-1", role: "admin" })),
);

// redirect() never returns in Next (it throws NEXT_REDIRECT); the mock mirrors
// that so the layout's control flow after the call stays honest.
const redirectMock = vi.hoisted(() =>
  vi.fn<(path: string) => never>((path: string): never => {
    throw new Error(`redirect:${path}`);
  }),
);

vi.mock("next/headers", () => ({ headers: async () => new Headers() }));
vi.mock("next/navigation", () => ({ redirect: redirectMock }));
vi.mock("@/lib/auth-guard", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth-guard")>();
  return { ...actual, requireAdmin: requireAdminMock };
});

import AdminLayout from "@/app/admin/layout";
import { AuthError } from "@/lib/auth-guard";

describe("admin layout (the authoritative page-side check, review item 9)", () => {
  it("renders its children for an admin", async () => {
    const element = (await AdminLayout({ children: <p>admin area</p> })) as React.ReactElement;
    render(element);
    expect(document.body).toHaveTextContent("admin area");
  });

  it("redirects to sign-in without a session (requireAdmin → 401)", async () => {
    requireAdminMock.mockRejectedValueOnce(new AuthError(401, "sign in required"));
    await expect(AdminLayout({ children: null })).rejects.toThrow("redirect:/sign-in");
    expect(redirectMock).toHaveBeenCalledWith("/sign-in");
  });

  it("redirects home for a signed-in non-admin (requireAdmin → 403)", async () => {
    requireAdminMock.mockRejectedValueOnce(new AuthError(403, "admin only"));
    await expect(AdminLayout({ children: null })).rejects.toThrow("redirect:/");
    expect(redirectMock).toHaveBeenCalledWith("/");
  });
});