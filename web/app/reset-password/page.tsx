"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { authClient } from "@/lib/auth-client";
import { Button, buttonVariants } from "@/components/ui/button";

// One page for both flows (ADR-0028): the invitee's set-password link and the
// forgot-password reset link both land here with ?token=…, and Better Auth
// itself verifies the token (single use, expiry) on submit. When Better Auth's
// own GET endpoint redirects a stale link here it adds ?error=INVALID_TOKEN
// (code review round 1 finding 4) — the page surfaces that as the invalid or
// expired message right away.
const INVALID_LINK_MESSAGE = "This link is invalid or has expired. Ask for a new one.";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    searchParams.get("error") === "INVALID_TOKEN" ? INVALID_LINK_MESSAGE : null,
  );
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const { error: resetError } = await authClient.resetPassword({ newPassword: password, token });
    if (resetError) {
      setError(INVALID_LINK_MESSAGE);
      setSubmitting(false);
      return;
    }
    setDone(true);
  }

  if (done) {
    return (
      <div className="flex w-full max-w-sm flex-col gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Password set</h1>
        <p className="text-sm">Your password has been changed. You can now sign in.</p>
        <Link href="/sign-in" className={buttonVariants()}>
          Go to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-3">
      <h1 className="text-xl font-semibold tracking-tight">Set a new password</h1>
      <label className="flex flex-col gap-1 text-sm">
        New password
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1.5"
          name="password"
        />
      </label>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={submitting || !token}>
        {submitting ? "Setting…" : "Set password"}
      </Button>
      <Link href="/sign-in" className="text-sm text-primary underline-offset-4 hover:underline">
        Back to sign in
      </Link>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="mx-auto flex max-w-5xl justify-center px-4 py-10">
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </main>
  );
}