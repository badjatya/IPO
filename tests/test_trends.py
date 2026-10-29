import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, TempRepo  # noqa: E402

from ipo_agent import trends  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def seen(day, hour=12, minute=0):
    return dt.datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}:00+05:30")


def ipo(key="acme", **fields):
    base = {"key": key, "name": "Acme Industries", "phase": "open"}
    base.update(fields)
    return base


class GmpTimeTests(NoNetworkCase):
    def test_reads_investorgain_time_in_the_snapshot_year(self):
        self.assertEqual(
            trends._gmp_time("13-Oct 23:37", seen("2026-10-14", 9, 7)),
            dt.datetime(2026, 10, 13, 23, 37, tzinfo=IST),
        )

    def test_december_reading_seen_in_january_rolls_back_a_year(self):
        self.assertEqual(
            trends._gmp_time("31-Dec 18:00", seen("2027-01-02", 9, 7)),
            dt.datetime(2026, 12, 31, 18, 0, tzinfo=IST),
        )

    def test_unparseable_or_missing_time_falls_back_to_snapshot_time(self):
        at = seen("2026-10-14", 9, 7)
        self.assertEqual(trends._gmp_time(None, at), at)
        self.assertEqual(trends._gmp_time("not a time", at), at)


class GmpTrendTests(NoNetworkCase):
    def history(self, gmp_by_day):
        return [(seen(f"2026-11-{day:02d}", 12), ipo(gmp=gmp, gmp_updated=f"{day:02d}-Nov 11:00"))
                for day, gmp in gmp_by_day]

    def test_needs_two_days(self):
        self.assertIsNone(trends.gmp_trend([]))
        self.assertIsNone(trends.gmp_trend(self.history([(1, 10)])))
        self.assertIsNone(trends.gmp_trend([(seen("2026-11-01"), ipo(gmp=None))]))

    def test_last_reading_of_each_day_wins(self):
        history = [
            (seen("2026-11-01", 9), ipo(gmp=10, gmp_updated="01-Nov 08:00")),
            (seen("2026-11-01", 19), ipo(gmp=20, gmp_updated="01-Nov 18:30")),
            (seen("2026-11-02", 19), ipo(gmp=30, gmp_updated="02-Nov 18:30")),
        ]
        result = trends.gmp_trend(history)
        self.assertEqual([p["gmp"] for p in result["points"]], [20, 30])
        self.assertEqual(result["points"][0]["date"], "2026-11-01")

    def test_rising_above_eight_percent(self):
        result = trends.gmp_trend(self.history([(1, 100), (2, 130)]))
        self.assertEqual(result["direction"], "up")
        self.assertIn("rising", result["text"])

    def test_move_below_eight_percent_is_steady(self):
        result = trends.gmp_trend(self.history([(1, 100), (2, 107)]))
        self.assertEqual(result["direction"], "flat")
        self.assertIn("steady", result["text"])

    def test_move_must_also_clear_one_percent_of_price(self):
        history = self.history([(1, 100), (2, 110)])
        self.assertEqual(trends.gmp_trend(history, price=1000)["direction"], "up")
        self.assertEqual(trends.gmp_trend(history, price=5000)["direction"], "flat")

    def test_falling_is_measured_from_the_peak(self):
        result = trends.gmp_trend(self.history([(1, 50), (2, 90), (3, 70)]))
        self.assertEqual(result["direction"], "down")
        self.assertIn("falling (peak ₹90)", result["text"])

    def test_falling_between_first_and_last(self):
        result = trends.gmp_trend(self.history([(1, 90), (2, 50)]))
        self.assertEqual(result["direction"], "down")
        self.assertIn("falling", result["text"])

    def test_window_drops_points_older_than_seven_days(self):
        history = self.history([(1, 10), (10, 20)])
        # Day 1 is outside the 7-day window, leaving one point: no trend.
        self.assertIsNone(trends.gmp_trend(history))

    def test_text_is_capped_at_five_points(self):
        history = self.history([(day, day * 10) for day in range(1, 7)])
        result = trends.gmp_trend(history)
        self.assertEqual(len(result["points"]), 6)
        self.assertIn("…", result["text"])
        self.assertEqual(result["text"].count("→"), 4)


class SubscriptionTrendTests(NoNetworkCase):
    def history(self, readings, open_=None, close=None):
        out = []
        for at, times in readings:
            out.append((at, ipo(open=open_, close=close, subscription={
                key: {"times": value} for key, value in times.items()
            })))
        return out

    def test_needs_open_date_and_two_days(self):
        self.assertIsNone(trends.subscription_trend([], None, None))
        history = self.history([(seen("2026-10-27", 12), {"retail": 1})], "2026-10-27", "2026-10-29")
        self.assertIsNone(trends.subscription_trend(history, "2026-10-27", "2026-10-29"))

    def test_run_before_ten_ist_counts_as_previous_weekday(self):
        history = self.history([
            (seen("2026-10-27", 11), {"retail": 1.0}),
            (seen("2026-10-28", 9), {"retail": 2.0}),
            (seen("2026-10-28", 11), {"retail": 3.0}),
        ], "2026-10-27", "2026-10-29")
        result = trends.subscription_trend(history, "2026-10-27", "2026-10-29")
        self.assertEqual(result["days"][0]["day"], 1)
        self.assertEqual(result["days"][0]["date"], "2026-10-27")
        self.assertEqual(result["days"][0]["times"]["retail"], 2.0)
        self.assertEqual(result["days"][1]["times"]["retail"], 3.0)

    def test_weekend_run_before_ten_uses_friday(self):
        history = self.history([
            (seen("2026-10-29", 11), {"retail": 1.0}),
            (seen("2026-10-31", 9), {"retail": 3.0}),
        ], "2026-10-27", "2026-11-03")
        result = trends.subscription_trend(history, "2026-10-27", "2026-11-03")
        self.assertEqual(result["days"][-1]["date"], "2026-10-30")

    def test_run_after_the_close_day_counts_as_the_close_day(self):
        history = self.history([
            (seen("2026-10-28", 11), {"retail": 1.0}),
            (seen("2026-11-05", 11), {"retail": 9.0}),
        ], "2026-10-27", "2026-11-03")
        result = trends.subscription_trend(history, "2026-10-27", "2026-11-03")
        self.assertEqual(result["days"][-1]["date"], "2026-11-03")

    def test_day_numbers_count_weekdays_only(self):
        # Mon 26 Oct -> Wed 28 Oct is day 3; the weekend is skipped.
        self.assertEqual(trends._bidding_day(dt.date(2026, 10, 26), dt.date(2026, 10, 28)), 3)
        self.assertEqual(trends._bidding_day(dt.date(2026, 10, 26), dt.date(2026, 11, 2)), 6)

    def test_weekday_exchange_holiday_still_counts_as_a_bidding_day(self):
        # Documented in trends.py: "an exchange holiday mid-issue makes it run ahead".
        # Nothing in the agent knows the holiday calendar, so a weekday holiday counts.
        self.assertEqual(trends._bidding_day(dt.date(2026, 10, 26), dt.date(2026, 10, 29)), 4)

    def test_categories_missing_on_a_day_are_left_out_of_the_text(self):
        history = self.history([
            (seen("2026-10-27", 11), {"retail": 1.0, "total": 1.0}),
            (seen("2026-10-28", 11), {"total": 2.0}),
        ], "2026-10-27", "2026-10-29")
        result = trends.subscription_trend(history, "2026-10-27", "2026-10-29")
        self.assertNotIn("Retail", result["text"])
        self.assertIn("Total 1x → 2x", result["text"])

    def test_close_is_optional(self):
        history = self.history([
            (seen("2026-10-27", 11), {"retail": 1.0}),
            (seen("2026-10-28", 11), {"retail": 2.0}),
        ], "2026-10-27", None)
        result = trends.subscription_trend(history, "2026-10-27", None)
        self.assertEqual(result["days"][-1]["date"], "2026-10-28")


class TrendWrapperTests(NoNetworkCase):
    def test_returns_both_trends(self):
        entry = ipo(open="2026-10-27", close="2026-10-29", price_high=330)
        result = trends.trend(entry, [])
        self.assertEqual(result, {"gmp": None, "subscription": None})


class LoadAndAttachTests(NoNetworkCase):
    def test_load_returns_snapshots_oldest_first(self):
        with TempRepo() as repo:
            repo.snapshot("2026-10-28T0907", [ipo(gmp=10, gmp_updated="28-Oct 08:00")])
            repo.snapshot("2026-10-27T0907", [ipo(gmp=9, gmp_updated="27-Oct 08:00")])
            loaded = trends.load(repo.path("data", "snapshots"))
            self.assertEqual([s["generated_at"] for s in loaded],
                             ["2026-10-27T09:07+05:30", "2026-10-28T09:07+05:30"])

    def test_attach_uses_only_earlier_snapshots_and_the_snapshot_itself(self):
        with TempRepo() as repo:
            repo.snapshot("2026-10-27T0907", [ipo(gmp=10, gmp_updated="27-Oct 08:00")])
            repo.snapshot("2026-10-30T0907", [ipo(gmp=99, gmp_updated="30-Oct 08:00")])
            current = {
                "generated_at": "2026-10-28T09:07+05:30", "date": "2026-10-28", "errors": {},
                "ipos": [ipo(gmp=20, gmp_updated="28-Oct 08:00")],
            }
            trends.attach(current, repo.path("data", "snapshots"))
            gmp = current["ipos"][0]["trend"]["gmp"]
            self.assertEqual([p["gmp"] for p in gmp["points"]], [10, 20])
            self.assertEqual(gmp["direction"], "up")


if __name__ == "__main__":
    unittest.main()
