import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AdminSettingsPage from "@/app/admin/settings/page";

// The page is tested with fetch mocked (invite-page pattern): the mount GET
// answer, then the POST answer per test. The admin layout's guard is 010's and
// is covered by its own tests, so the page itself carries no guard.
const fetchMock = vi.hoisted(() => vi.fn<() => Promise<Response>>());

const seededRow = {
  key: "ask_daily_limit_per_user",
  value: 5,
  description: "How many Ask questions each person can send per day",
  updatedAt: null,
  updatedBy: null,
  updatedByEmail: null,
};

const changedRow = {
  key: "analysis_refresh_after_days",
  value: 30,
  description: "A saved analysis older than this many days is refreshed",
  updatedAt: "2026-10-29T09:30:00.000Z",
  updatedBy: "u-1",
  updatedByEmail: "admin@example.com",
};

const unknownRow = {
  key: "future_platform_flag",
  value: "on",
  description: "A row inserted by hand, not in the app's known keys",
  updatedAt: null,
  updatedBy: null,
  updatedByEmail: null,
};

function rowsResponse(rows: unknown[]): Response {
  return new Response(JSON.stringify({ settings: rows }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("admin settings page", () => {
  it("renders every row with its value, description and change line", async () => {
    fetchMock.mockResolvedValueOnce(rowsResponse([seededRow, changedRow, unknownRow]));
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);

    expect(await screen.findByText("Current value: 5")).toBeTruthy();
    expect(screen.getByText("How many Ask questions each person can send per day")).toBeTruthy();
    expect(screen.getByText("Current value: 30")).toBeTruthy();
    expect(screen.getByText(/A saved analysis older than this many days/)).toBeTruthy();
    expect(screen.getAllByText("Seeded")).toHaveLength(2); // the seeded and the unknown-key rows
    expect(screen.getByText(/Changed by admin@example.com on \d/)).toBeTruthy();
    expect((screen.getByLabelText("ask_daily_limit_per_user") as HTMLInputElement).value).toBe("5");
    expect((screen.getByLabelText("analysis_refresh_after_days") as HTMLInputElement).value).toBe("30");
  });

  it("editing a row posts exactly { key, value } with value a number, then shows the saved row", async () => {
    fetchMock
      .mockResolvedValueOnce(rowsResponse([seededRow, changedRow]))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            settings: {
              ...seededRow,
              value: 7,
              updatedAt: "2026-10-30T10:15:00.000Z",
              updatedBy: "u-1",
              updatedByEmail: "admin@example.com",
            },
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);
    await screen.findByLabelText("ask_daily_limit_per_user");

    fireEvent.change(screen.getByLabelText("ask_daily_limit_per_user"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ask_daily_limit_per_user" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith("/api/admin/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "ask_daily_limit_per_user", value: 7 }),
      }),
    );
    // The posted body is exactly { key, value } and value is a real number,
    // not the input's string.
    const [, postArgs] = fetchMock.mock.calls[1];
    const body = JSON.parse((postArgs as { body: string }).body) as { key: string; value: unknown };
    expect(body).toEqual({ key: "ask_daily_limit_per_user", value: 7 });
    expect(typeof body.value).toBe("number");

    expect(await screen.findByText("Current value: 7")).toBeTruthy();
    expect(screen.getByText(/Changed by admin@example.com on 30 Oct 2026/)).toBeTruthy();
    expect(screen.getByText("Saved")).toBeTruthy();
  });

  it("an empty input never posts", async () => {
    fetchMock.mockResolvedValueOnce(rowsResponse([seededRow]));
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);
    const input = await screen.findByLabelText("ask_daily_limit_per_user");

    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ask_daily_limit_per_user" }));
    // The required attribute blocks the submit; without it, the guard below
    // would. Either way: one request only, the mount GET.
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Direct submit exercises the page's own guard (jsdom's interactive
    // validation would otherwise swallow the submit).
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(await screen.findByText("Enter a whole number")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("a non-numeric input never posts", async () => {
    fetchMock.mockResolvedValueOnce(rowsResponse([seededRow]));
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);
    const input = await screen.findByLabelText("ask_daily_limit_per_user");

    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ask_daily_limit_per_user" }));
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the mount GET
  });

  it("a row with a key outside KNOWN_SETTINGS renders read-only with the label and no input", async () => {
    fetchMock.mockResolvedValueOnce(rowsResponse([unknownRow]));
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);

    expect(await screen.findByText("future_platform_flag")).toBeTruthy();
    expect(screen.getByText("A row inserted by hand, not in the app's known keys")).toBeTruthy();
    expect(screen.getByText("Not in the app's list of known keys")).toBeTruthy();
    expect(screen.queryByLabelText("future_platform_flag")).toBeNull();
    expect(screen.queryByRole("button", { name: /Save/ })).toBeNull();
  });

  it("a 400 response shows the server's error and keeps the old value", async () => {
    fetchMock
      .mockResolvedValueOnce(rowsResponse([seededRow]))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: "value must be at least 0" }), {
          status: 400,
          headers: { "content-type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminSettingsPage />);
    await screen.findByLabelText("ask_daily_limit_per_user");

    fireEvent.change(screen.getByLabelText("ask_daily_limit_per_user"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Save ask_daily_limit_per_user" }));

    expect(await screen.findByText("value must be at least 0")).toBeTruthy();
    expect(screen.getByText("Current value: 5")).toBeTruthy(); // old value kept
    expect(screen.queryByText("Saved")).toBeNull();
  });
});