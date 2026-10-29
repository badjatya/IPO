import { afterEach, describe, expect, it, vi } from "vitest";
import { DISCLAIMER } from "@/lib/site";

// The credential-account lookup is a database query; the hook-wording tests
// control it through this mock (review item 8). The Resend SDK is replaced so
// "Resend mode" tests never touch the network.
const state = vi.hoisted(() => ({
  hasCredentialAccount: false,
  resendSend: vi.fn<() => Promise<{ data: { id: string } | null; error: unknown } | null>>(
    async () => ({ data: { id: "mail-1" }, error: null }),
  ),
}));

vi.mock("@/lib/db", () => ({
  db: () => ({
    select: () => ({
      from: () => ({
        where: () => ({
          limit: async () => (state.hasCredentialAccount ? [{ id: "acc-1" }] : []),
        }),
      }),
    }),
  }),
}));

vi.mock("resend", () => ({
  Resend: class {
    emails = { send: state.resendSend };
  },
}));

import {
  assertMailConfig,
  buildAccountEmail,
  sendAccountEmail,
  sendResetPasswordMail,
} from "@/lib/mail";

afterEach(() => {
  vi.unstubAllEnvs();
  state.hasCredentialAccount = false;
  state.resendSend.mockClear();
});

describe("account email wording (review item 8)", () => {
  const url = "http://localhost:3000/reset-password/abc123";

  it("invite wording carries the link, the product name and the disclaimer", () => {
    const { subject, text } = buildAccountEmail("invite", url);
    expect(subject).toContain("Set up");
    expect(text).toContain("invited");
    expect(text).toContain(url);
    expect(text).toContain(DISCLAIMER);
  });

  it("reset wording differs from the invite wording", () => {
    const { subject, text } = buildAccountEmail("reset", url);
    expect(subject).toContain("Reset");
    expect(text).toContain("new password");
    expect(text).toContain(url);
    expect(text).toContain(DISCLAIMER);
    expect(text).not.toContain("invited");
  });
});

describe("sendResetPasswordMail", () => {
  it("sends invite wording to a user with no credential account yet", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "");
    state.hasCredentialAccount = false;
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    await sendResetPasswordMail({ user: { id: "u-1", email: "a@example.com" }, url: "http://localhost:3000/reset-password/tok" });
    expect(log).toHaveBeenCalledWith(expect.stringContaining("to=a@example.com"));
    expect(log).toHaveBeenCalledWith(expect.stringContaining("subject=Set up"));
    expect(log).toHaveBeenCalledWith(expect.stringContaining("invited"));
    log.mockRestore();
  });

  it("sends reset wording to a user who has a credential account", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "");
    state.hasCredentialAccount = true;
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    await sendResetPasswordMail({ user: { id: "u-1", email: "a@example.com" }, url: "http://localhost:3000/reset-password/tok" });
    expect(log).toHaveBeenCalledWith(expect.stringContaining("subject=Reset"));
    expect(log).toHaveBeenCalledWith(expect.stringContaining("new password"));
    log.mockRestore();
  });

  it("does not await delivery and does not throw when delivery fails", async () => {
    // The hook fires the mail without awaiting (review item 10): a delivery
    // error must reach the log, never the requester.
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "re_test_key");
    vi.stubEnv("EMAIL_FROM", "no-reply@example.com");
    state.resendSend.mockRejectedValueOnce(new Error("resend is down"));
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(
      sendResetPasswordMail({ user: { id: "u-1", email: "a@example.com" }, url: "http://localhost:3000/reset-password/tok" }),
    ).resolves.toBeUndefined();
    // The fired promise settles after the hook returns; wait for the log.
    await vi.waitFor(() => expect(errorLog).toHaveBeenCalledWith(expect.stringContaining("failed to send account email"), expect.any(Error)));
    errorLog.mockRestore();
  });
});

describe("sendAccountEmail", () => {
  it("print mode prints to, subject and body, outside production (review item 5)", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "");
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    await sendAccountEmail({ to: "a@example.com", subject: "Subject line", text: "Body text", html: "<p>Body text</p>" });
    expect(log).toHaveBeenCalledWith(expect.stringContaining("to=a@example.com"));
    expect(log).toHaveBeenCalledWith(expect.stringContaining("subject=Subject line"));
    expect(log).toHaveBeenCalledWith(expect.stringContaining("Body text"));
    log.mockRestore();
  });

  it("sends through the Resend SDK when the key is set", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("RESEND_API_KEY", "re_test_key");
    vi.stubEnv("EMAIL_FROM", "no-reply@example.com");
    await sendAccountEmail({ to: "a@example.com", subject: "S", text: "T", html: "<p>T</p>" });
    expect(state.resendSend).toHaveBeenCalledWith(
      expect.objectContaining({
        from: "no-reply@example.com",
        to: "a@example.com",
        subject: "S",
        text: "T",
        html: "<p>T</p>",
      }),
    );
  });

  it("throws in production without the mail config — a live token never prints (review item 5)", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("EMAIL_FROM", "");
    await expect(
      sendAccountEmail({ to: "a@example.com", subject: "S", text: "T", html: "<p>T</p>" }),
    ).rejects.toThrow(/email is not configured/);
    expect(() => assertMailConfig()).toThrow(/email is not configured/);
  });
});