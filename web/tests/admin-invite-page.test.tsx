import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AdminInvitePage from "@/app/admin/invite/page";

const authClientMock = vi.hoisted(() => ({
  signIn: { email: vi.fn<() => Promise<{ data: null | object; error: null | { message: string } }>>(async () => ({ data: null, error: null })) },
  requestPasswordReset: vi.fn<() => Promise<{ data: null | object; error: null | { message: string } }>>(async () => ({ data: null, error: null })),
  resetPassword: vi.fn<() => Promise<{ data: null | object; error: null | { message: string } }>>(async () => ({ data: null, error: null })),
  signOut: vi.fn<() => Promise<{ data: null | object; error: null | { message: string } }>>(async () => ({ data: null, error: null })),
}));

vi.mock("@/lib/auth-client", () => ({ authClient: authClientMock }));

const fetchMock = vi.hoisted(() => vi.fn<() => Promise<Response>>());

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});

describe("admin invite page", () => {
  it("posts the email and name to /api/admin/invite and confirms", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, message: "Invite sent" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminInvitePage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Name (optional)"), { target: { value: "New Person" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invite" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/admin/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "new@example.com", name: "New Person" }),
      }),
    );
    expect(await screen.findByText("Invite sent")).toBeTruthy();
  });

  it("signs out through the client when the sign-out control is clicked", async () => {
    const assign = vi.fn<() => void>();
    Object.defineProperty(window, "location", { configurable: true, value: { assign } });
    render(<AdminInvitePage />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(authClientMock.signOut).toHaveBeenCalled());
  });
});