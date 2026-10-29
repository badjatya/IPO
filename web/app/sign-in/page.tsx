"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { authClient } from "@/lib/auth-client";
import { safeNextPath } from "@/lib/safe-next";
import { Button } from "@/components/ui/button";

function SignInForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const { error: signInError } = await authClient.signIn.email({ email, password });
    if (signInError) {
      setError("The email or password is wrong.");
      setSubmitting(false);
      return;
    }
    const next = searchParams.get("next");
    // Same-site only: a crafted `next` must never send a freshly signed-in
    // user off the site (code review round 1 finding 3).
    window.location.assign(safeNextPath(next, window.location.origin));
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-3">
      <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
      <label className="flex flex-col gap-1 text-sm">
        Email
        <input
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1.5"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Password
        <input
          type="password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1.5"
        />
      </label>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
      <Link href="/forgot-password" className="text-sm text-primary underline-offset-4 hover:underline">
        Forgot your password?
      </Link>
    </form>
  );
}

export default function SignInPage() {
  return (
    <main className="mx-auto flex max-w-5xl justify-center px-4 py-10">
      <Suspense fallback={null}>
        <SignInForm />
      </Suspense>
    </main>
  );
}