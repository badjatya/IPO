import { Resend } from "resend";
import { account } from "@/db/schema";
import { db } from "@/lib/db";
import { DISCLAIMER, PRODUCT_NAME } from "@/lib/site";
import { and, eq } from "drizzle-orm";

// The only email path in the app (ADR-0028): Better Auth's reset-password hook
// is the single caller, so "no alert digests, no other email" is structural.
// Account emails carry only the two wordings (invite vs reset — review item 8),
// the product's placeholder name, the one-time link and the ADR-0012 disclaimer
// line. Never research content.

export interface AccountEmail {
  to: string;
  subject: string;
  text: string;
  html: string;
}

/**
 * Production cannot deliver account email. A named class, not a message-text
 * match: the invite route answers 500 on `instanceof`, so rewording the
 * message can never silently turn it into an "internal error" (code review
 * round 1 finding 7).
 */
export class MailNotConfiguredError extends Error {
  constructor(missing: string[]) {
    super(`account email is not configured (missing ${missing.join(", ")})`);
    this.name = "MailNotConfiguredError";
  }
}

/**
 * Throws when the app cannot deliver account email in this environment.
 * Outside production a missing key falls back to print mode, so only
 * production actually needs the config (review item 5; round 2 item 4: called
 * up front by the invite route, and in production at server start by lib/auth).
 */
export function assertMailConfig(): void {
  if (process.env.NODE_ENV !== "production") return;
  const missing: string[] = [];
  if (!process.env.RESEND_API_KEY) missing.push("RESEND_API_KEY");
  if (!process.env.EMAIL_FROM) missing.push("EMAIL_FROM");
  if (missing.length > 0) {
    throw new MailNotConfiguredError(missing);
  }
}

/** The two wordings the one hook can send (review item 8). */
export type AccountEmailKind = "invite" | "reset";

export function buildAccountEmail(kind: AccountEmailKind, url: string): Pick<AccountEmail, "subject" | "text" | "html"> {
  const subject = kind === "invite" ? `Set up your ${PRODUCT_NAME} account` : `Reset your ${PRODUCT_NAME} password`;
  const message =
    kind === "invite"
      ? "You've been invited. Follow the link below to set a password and sign in."
      : "Follow the link below to choose a new password.";
  const text = `${PRODUCT_NAME}\n\n${message}\n\n${url}\n\n${DISCLAIMER}`;
  const html =
    `<p>${PRODUCT_NAME}</p><p>${message}</p><p><a href="${url}">${url}</a></p><p>${DISCLAIMER}</p>`;
  return { subject, text, html };
}

/**
 * Does the user already have a credential account? The hook routes on this:
 * no credential row yet means the email is an invite (the user can never have
 * reset a password they don't have), any credential row means a reset
 * (review item 8).
 */
export async function hasCredentialAccount(userId: string): Promise<boolean> {
  const rows = await db()
    .select({ id: account.id })
    .from(account)
    .where(and(eq(account.userId, userId), eq(account.providerId, "credential")))
    .limit(1);
  return rows.length > 0;
}

/**
 * Better Auth's `emailAndPassword.sendResetPassword` hook. Picks the wording by
 * "has a credential account", then fires the mail without awaiting delivery
 * (review item 10): the public forgot-password response must never wait on
 * Resend, or a slow delivery would reveal that the address exists. Failures
 * land in the server log; nothing is shown to the requester. (There is no
 * host waitUntil on our Node runtime, so the fired promise with `.catch` is
 * the fallback the plan names for a version without `advanced.backgroundTasks`.)
 */
export async function sendResetPasswordMail(
  data: { user: { id: string; email: string }; url: string },
  _request?: Request,
): Promise<void> {
  const kind: AccountEmailKind = (await hasCredentialAccount(data.user.id)) ? "reset" : "invite";
  const email: AccountEmail = { to: data.user.email, ...buildAccountEmail(kind, data.url) };
  void sendAccountEmail(email).catch((error: unknown) => {
    console.error("[mail] failed to send account email:", error);
  });
}

/**
 * Delivers one account email. In production the config is mandatory (and
 * already checked up front); outside production a missing `RESEND_API_KEY`
 * prints the rendered email to the server console instead — a live one-time
 * token must never print anywhere in production (review item 5).
 */
export async function sendAccountEmail(email: AccountEmail): Promise<void> {
  if (process.env.NODE_ENV === "production") assertMailConfig();
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.log(`[mail:print] to=${email.to} subject=${email.subject}\n${email.text}`);
    return;
  }
  const resend = new Resend(apiKey);
  const { error } = await resend.emails.send({
    from: process.env.EMAIL_FROM!,
    to: email.to,
    subject: email.subject,
    text: email.text,
    html: email.html,
  });
  if (error) throw error;
}