"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";

// The minimal admin invite form (the settings page is task 013). Sign-out
// lives here too — the only authenticated page in 010.
async function onSignOut() {
  await authClient.signOut();
  window.location.assign("/sign-in");
}

export default function AdminInvitePage() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setMessage(null);
    const response = await fetch("/api/admin/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name }),
    });
    const data = (await response.json().catch(() => null)) as { error?: string } | null;
    setSubmitting(false);
    if (response.ok) {
      setMessage("Invite sent");
      setEmail("");
      setName("");
    } else {
      setError(data?.error ?? "Invite failed");
    }
  }

  return (
    <main className="mx-auto flex max-w-5xl justify-center px-4 py-10">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Invite a user</h1>
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
        <label className="flex flex-col gap-1 text-sm">
          Name (optional)
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="rounded-md border border-input bg-background px-2 py-1.5"
            name="name"
          />
        </label>
        {message && <p className="text-sm text-emerald-600">{message}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={submitting}>
          {submitting ? "Sending…" : "Send invite"}
        </Button>
        <Button type="button" variant="outline" onClick={onSignOut}>
          Sign out
        </Button>
      </form>
    </main>
  );
}