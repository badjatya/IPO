"use client";

import { useState } from "react";
import Link from "next/link";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";

// The identical message for every address: whether or not an account exists,
// the page answers the same, and no email goes to an unknown address
// (ADR-0028). The server decides silently.
const ALWAYS_THE_SAME = "If an account exists for this email, a link is on its way.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    // redirectTo points at the app's reset page; Better Auth validates the
    // token server-side and lands the browser there with ?token=….
    await authClient.requestPasswordReset({ email, redirectTo: "/reset-password" });
    setSent(true);
    setSubmitting(false);
  }

  return (
    <main className="mx-auto flex max-w-5xl justify-center px-4 py-10">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Forgot your password?</h1>
        {sent ? (
          <output className="text-sm">{ALWAYS_THE_SAME}</output>
        ) : (
          <>
            <label className="flex flex-col gap-1 text-sm">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="rounded-md border border-input bg-background px-2 py-1.5"
                name="email"
              />
            </label>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Sending…" : "Send reset link"}
            </Button>
            <Link href="/sign-in" className="text-sm text-primary underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </>
        )}
      </form>
    </main>
  );
}