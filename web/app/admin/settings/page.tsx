"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { KNOWN_SETTINGS } from "@/lib/settings";

// The admin settings page (task 013). The admin layout (`web/app/admin/
// layout.tsx`) is the authoritative page-side guard for every /admin/* page, so
// this page only renders and posts. It lists every `settings` row (GET returns
// all of them) and edits one at a time; a row whose key is not in the app's
// known-keys list is shown read-only, because every save of it is refused. The
// POST body is exactly { key, value } with value a JSON number — an empty or
// non-numeric input is blocked here, before any request.
interface SettingRow {
  key: string;
  value: unknown;
  description: string;
  updatedAt: string | null;
  updatedBy: string | null;
  updatedByEmail: string | null;
}

const IST_FORMATTER = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Kolkata",
});

function istTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return IST_FORMATTER.format(date);
}

function changedByLine(row: SettingRow): string {
  if (row.updatedBy === null || row.updatedBy === undefined) return "Seeded";
  const when = row.updatedAt ? ` on ${istTimestamp(row.updatedAt)}` : "";
  const who = row.updatedByEmail ?? "an unknown account";
  return `Changed by ${who}${when}`;
}

export default function AdminSettingsPage() {
  const [rows, setRows] = useState<SettingRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<Record<string, string>>({});
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/admin/settings")
      .then(async (response) => {
        if (!response.ok) throw new Error("failed to load settings");
        const data = (await response.json()) as { settings: SettingRow[] };
        if (!cancelled) setRows(data.settings);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Could not load settings");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSave(event: React.FormEvent<HTMLFormElement>, rowKey: string) {
    event.preventDefault();
    setSavedKey(null);
    const raw = String(new FormData(event.currentTarget).get("value") ?? "").trim();
    if (raw === "" || !Number.isInteger(Number(raw))) {
      // Blocked before any POST: an empty or non-numeric input never posts.
      setSaveError((prev) => ({ ...prev, [rowKey]: "Enter a whole number" }));
      return;
    }
    if (savingKey !== null) return; // one save at a time
    setSavingKey(rowKey);
    setSaveError((prev) => ({ ...prev, [rowKey]: "" }));
    try {
      const response = await fetch("/api/admin/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: rowKey, value: Number(raw) }),
      });
      const data = (await response.json().catch(() => null)) as
        | { settings?: SettingRow; error?: string }
        | null;
      const savedRow = data?.settings;
      if (response.ok && savedRow) {
        setRows((current) => (current ?? []).map((row) => (row.key === rowKey ? savedRow : row)));
        setSavedKey(rowKey);
      } else {
        setSaveError((prev) => ({ ...prev, [rowKey]: data?.error ?? "Save failed" }));
      }
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Quotas and caps come from these rows. Each value is checked against the
        app&apos;s list of known keys and types before it is saved.
      </p>
      {loadError && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {loadError}
        </p>
      )}
      {rows === null && !loadError && (
        <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
      )}
      {rows && (
        <div className="mt-6 flex flex-col gap-8">
          {rows.map((row) => {
            const spec = KNOWN_SETTINGS[row.key];
            return (
              <section key={row.key} className="max-w-xl">
                <h2 className="text-base font-semibold tracking-tight">{row.key}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{row.description}</p>
                <p className="mt-2 text-sm">Current value: {String(row.value)}</p>
                <p className="text-sm text-muted-foreground">{changedByLine(row)}</p>
                {spec === undefined ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Not in the app&apos;s list of known keys
                  </p>
                ) : (
                  <form onSubmit={(event) => onSave(event, row.key)} className="mt-3 flex max-w-sm flex-col gap-3">
                    <label className="flex flex-col gap-1 text-sm">
                      {row.key}
                      <input
                        type="number"
                        name="value"
                        min={spec.min}
                        step={1}
                        required
                        defaultValue={typeof row.value === "number" ? String(row.value) : ""}
                        className="rounded-md border border-input bg-background px-2 py-1.5"
                      />
                    </label>
                    {saveError[row.key] && (
                      <p role="alert" className="text-sm text-destructive">
                        {saveError[row.key]}
                      </p>
                    )}
                    {savedKey === row.key && (
                      <p className="text-sm text-emerald-600">Saved</p>
                    )}
                    <Button type="submit" disabled={savingKey !== null}>
                      {savingKey === row.key ? "Saving…" : `Save ${row.key}`}
                    </Button>
                  </form>
                )}
              </section>
            );
          })}
        </div>
      )}
    </main>
  );
}