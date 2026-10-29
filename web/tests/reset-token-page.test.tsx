import { describe, expect, it, vi } from "vitest";

// redirect() never returns in Next (it throws NEXT_REDIRECT); the mock mirrors
// that, the same pattern as admin-layout.test.tsx.
const redirectMock = vi.hoisted(() =>
  vi.fn<(path: string) => never>((path: string): never => {
    throw new Error(`redirect:${path}`);
  }),
);

vi.mock("next/navigation", () => ({ redirect: redirectMock }));

import ResetPasswordTokenPage from "@/app/reset-password/[token]/page";

describe("reset-password/[token] (1.7.14's emailed link shape)", () => {
  it("redirects to the form page with the token in ?token=", async () => {
    await expect(
      ResetPasswordTokenPage({ params: Promise.resolve({ token: "abc-123" }) }),
    ).rejects.toThrow("redirect:/reset-password?token=abc-123");
    expect(redirectMock).toHaveBeenCalledWith("/reset-password?token=abc-123");
  });

  it("url-encodes tokens with unsafe characters", async () => {
    await ResetPasswordTokenPage({ params: Promise.resolve({ token: "a/b c" }) }).catch(() => {});
    expect(redirectMock).toHaveBeenCalledWith("/reset-password?token=a%2Fb%20c");
  });
});