import { describe, expect, it } from "vitest";
import { KNOWN_SETTINGS, validateSettingValue } from "@/lib/settings";

describe("KNOWN_SETTINGS", () => {
  it("registers exactly the four keys with db.md's bounds", () => {
    expect(Object.keys(KNOWN_SETTINGS).sort()).toEqual([
      "analysis_daily_limit_platform",
      "analysis_monthly_limit_per_user",
      "analysis_refresh_after_days",
      "ask_daily_limit_per_user",
    ]);
    expect(KNOWN_SETTINGS.ask_daily_limit_per_user.min).toBe(0);
    expect(KNOWN_SETTINGS.analysis_monthly_limit_per_user.min).toBe(0);
    expect(KNOWN_SETTINGS.analysis_daily_limit_platform.min).toBe(0);
    expect(KNOWN_SETTINGS.analysis_refresh_after_days.min).toBe(1);
  });
});

describe("validateSettingValue", () => {
  it("accepts each key at its minimum and at a larger integer", () => {
    expect(validateSettingValue({ key: "ask_daily_limit_per_user", value: 0 })).toEqual({
      ok: true,
      key: "ask_daily_limit_per_user",
      value: 0,
    });
    expect(validateSettingValue({ key: "ask_daily_limit_per_user", value: 5 })).toEqual({
      ok: true,
      key: "ask_daily_limit_per_user",
      value: 5,
    });
    expect(validateSettingValue({ key: "analysis_monthly_limit_per_user", value: 0 })).toMatchObject({
      ok: true,
      key: "analysis_monthly_limit_per_user",
      value: 0,
    });
    expect(validateSettingValue({ key: "analysis_daily_limit_platform", value: 100 })).toMatchObject({
      ok: true,
      key: "analysis_daily_limit_platform",
      value: 100,
    });
    expect(validateSettingValue({ key: "analysis_refresh_after_days", value: 1 })).toMatchObject({
      ok: true,
      key: "analysis_refresh_after_days",
      value: 1,
    });
    expect(validateSettingValue({ key: "analysis_refresh_after_days", value: 30 })).toMatchObject({
      ok: true,
      key: "analysis_refresh_after_days",
      value: 30,
    });
  });

  it("refuses a body that is not an object", () => {
    for (const body of ["5", 5.5, true, null, [1, 2]]) {
      const result = validateSettingValue(body);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toBe("body must be an object with key and value");
    }
  });

  it("refuses a value that is not a number (string, boolean, null, object, array)", () => {
    for (const value of ["5", true, null, { n: 1 }, [1]]) {
      const result = validateSettingValue({ key: "ask_daily_limit_per_user", value });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toBe("value must be a number");
    }
  });

  it("refuses a value that is not a whole number", () => {
    const result = validateSettingValue({ key: "ask_daily_limit_per_user", value: 5.5 });
    expect(result).toEqual({ ok: false, error: "value must be a whole number" });
  });

  it("refuses a value below the key's bound, naming the bound", () => {
    expect(validateSettingValue({ key: "ask_daily_limit_per_user", value: -1 })).toEqual({
      ok: false,
      error: "value must be at least 0",
    });
    expect(validateSettingValue({ key: "analysis_refresh_after_days", value: 0 })).toEqual({
      ok: false,
      error: "value must be at least 1",
    });
  });

  it("refuses an unknown key, a missing key, and a prototype key", () => {
    expect(validateSettingValue({ key: "not_a_real_key", value: 5 })).toEqual({
      ok: false,
      error: "unknown settings key",
    });
    expect(validateSettingValue({ value: 5 })).toEqual({ ok: false, error: "unknown settings key" });
    expect(validateSettingValue({ key: "constructor", value: 5 })).toEqual({
      ok: false,
      error: "unknown settings key",
    });
  });
});