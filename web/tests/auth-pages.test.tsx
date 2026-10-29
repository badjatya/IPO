import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ForgotPasswordPage from "@/app/forgot-password/page";
import ResetPasswordPage from "@/app/reset-password/page";
import SignInPage from "@/app/sign-in/page";

// The pages call the client, never the network.
type ClientResult = Promise<{ data: null | object; error: null | { message: string } }>;

const authClientMock = vi.hoisted(() => ({
  signIn: { email: vi.fn<() => ClientResult>(async () => ({ data: null, error: null })) },
  requestPasswordReset: vi.fn<() => ClientResult>(async () => ({ data: null, error: null })),
  resetPassword: vi.fn<() => ClientResult>(async () => ({ data: null, error: null })),
  signOut: vi.fn<() => ClientResult>(async () => ({ data: null, error: null })),
}));

vi.mock("@/lib/auth-client", () => ({ authClient: authClientMock }));

const searchParamsMock = vi.hoisted(() => ({ value: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(searchParamsMock.value),
}));

afterEach(() => {
  vi.clearAllMocks();
  searchParamsMock.value = "";
});

// jsdom can't navigate; the pages assign to window.location after a sign-in.
function stubLocationAssign() {
  const assign = vi.fn<() => void>();
  Object.defineProperty(window, "location", { configurable: true, value: { assign } });
  return assign;
}

describe("sign-in page", () => {
  it("renders the form and submits email and password to signIn.email", async () => {
    stubLocationAssign();
    render(<SignInPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(authClientMock.signIn.email).toHaveBeenCalledWith({ email: "a@example.com", password: "a-secret" }),
    );
  });

  it("shows an error on a failed sign-in", async () => {
    authClientMock.signIn.email.mockResolvedValueOnce({ data: null, error: { message: "invalid" } });
    render(<SignInPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("The email or password is wrong."));
  });

  it("links to the forgot-password page", () => {
    render(<SignInPage />);
    expect(screen.getByRole("link", { name: /forgot your password/i })).toHaveAttribute("href", "/forgot-password");
  });
});

describe("forgot-password page", () => {
  it("submits the email to requestPasswordReset with the app's reset path", async () => {
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    await waitFor(() =>
      expect(authClientMock.requestPasswordReset).toHaveBeenCalledWith({
        email: "a@example.com",
        redirectTo: "/reset-password",
      }),
    );
  });

  it("shows the identical message whether an account exists or not", async () => {
    // Resolve as if the address existed…
    authClientMock.requestPasswordReset.mockResolvedValueOnce({ data: { status: true }, error: null });
    const { unmount } = render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    const messageForKnownAddress = await screen.findByRole("status");

    // …then resolve as if it did not: the page must answer the same way.
    unmount();
    authClientMock.requestPasswordReset.mockResolvedValueOnce({ data: null, error: { message: "network" } });
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nobody@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    const messageForUnknownAddress = await screen.findByRole("status");

    expect(messageForKnownAddress.textContent).toBe(
      "If an account exists for this email, a link is on its way.",
    );
    expect(messageForUnknownAddress.textContent).toBe(messageForKnownAddress.textContent);
  });
});

describe("reset-password page", () => {
  it("submits the new password and the token to resetPassword", async () => {
    searchParamsMock.value = "token=invite-or-reset-token";
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "fresh-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    await waitFor(() =>
      expect(authClientMock.resetPassword).toHaveBeenCalledWith({
        newPassword: "fresh-secret",
        token: "invite-or-reset-token",
      }),
    );
  });

  it("links to sign-in on success", async () => {
    searchParamsMock.value = "token=abc123";
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "fresh-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    await waitFor(() => expect(screen.getByRole("link", { name: "Go to sign in" })).toHaveAttribute("href", "/sign-in"));
  });

  it("says the link is invalid or expired on failure", async () => {
    searchParamsMock.value = "token=bad-token";
    authClientMock.resetPassword.mockResolvedValueOnce({ data: null, error: { message: "invalid token" } });
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "fresh-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Set password" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("This link is invalid or has expired."),
    );
  });
});