import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase, TempRepo  # noqa: E402

from ipo_agent import outcomes  # noqa: E402

TODAY = "2026-10-29"


def history(**fields):
    base = {
        "name": "Acme Industries", "symbol": "ACME", "listing": "2026-10-21",
        "open": "2026-10-15", "close": "2026-10-20", "price_high": 100.0,
        "pe": 10.0, "size_cr": 50.0,
        "gmps": [{"at": "2026-10-20T19:09:00+05:30", "gmp": 20.0, "updated": "20-Oct 18:00"}],
    }
    base.update(fields)
    return base


def prices():
    return {"listed_on": "2026-10-21", "issue": 90.0, "listing": 110.0, "close": 120.0,
            "high": 130.0, "low": 100.0, "source": "nse"}


def sub():
    return {"source": "nse ipo-detail 2026-10-21",
            "data": {"qib": {"times": 3.0}, "retail": {"times": 2.0}, "total": {"times": 2.5}}}


class FakeNSE:
    def __init__(self, payload):
        self.payload = payload
        self.paths = []

    def api(self, path):
        self.paths.append(path)
        return self.payload


class FakeDetail:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def detail(self, symbol, series="EQ"):
        if self.error:
            raise self.error
        return self.result


class CollectTests(NoNetworkCase):
    def test_collects_fields_gmps_and_subscription_oldest_first(self):
        with TempRepo() as repo:
            repo.snapshot("2026-10-15T0907", [{
                "key": "acme", "name": "Acme Industries", "open": "2026-10-15",
                "close": "2026-10-20", "listing": "2026-10-21", "price_high": 100,
                "nse": {"symbol": "ACME", "series": "BE"}, "gmp": 10,
                "gmp_updated": "15-Oct 18:00",
                "subscription": {"total": {"times": 1.0}},
            }])
            repo.snapshot("2026-10-16T0907", [{
                "key": "acme", "gmp": 20, "gmp_updated": "16-Oct 18:00",
                "subscription": {"total": {"times": 2.0}},
            }])
            seen = outcomes.collect(repo.root)
        acme = seen["acme"]
        self.assertEqual(acme["name"], "Acme Industries")
        self.assertEqual(acme["symbol"], "ACME")
        self.assertEqual(acme["series"], "BE")
        self.assertEqual([g["gmp"] for g in acme["gmps"]], [10, 20])
        self.assertEqual(acme["sub"]["data"]["total"]["times"], 2.0)
        self.assertTrue(acme["sub"]["source"].startswith("snapshot 2026-10-16"))


class EveGmpTests(NoNetworkCase):
    def test_last_snapshot_before_listing_day(self):
        h = history(gmps=[
            {"at": "2026-10-19T19:00:00+05:30", "gmp": 10, "updated": "19-Oct"},
            {"at": "2026-10-20T19:00:00+05:30", "gmp": 20, "updated": "20-Oct"},
            {"at": "2026-10-21T19:00:00+05:30", "gmp": 30, "updated": "21-Oct"},
        ])
        self.assertEqual(outcomes.eve_gmp(h)["gmp"], 20)

    def test_no_snapshot_before_listing(self):
        h = history(gmps=[{"at": "2026-10-21T19:00:00+05:30", "gmp": 30, "updated": "21-Oct"}])
        self.assertIsNone(outcomes.eve_gmp(h))


class CallTests(NoNetworkCase):
    def test_last_report_up_to_the_close_day_am_and_card_fields(self):
        with TempRepo() as repo:
            repo.card("acme", {"anchor_grade": "strong", "summary": "card"})
            repo.report("2026-10-19-pm", {"ipos": {"acme": {"verdict": "neutral", "verdict_text": "Neutral"}}})
            repo.report("2026-10-20-am", {"ipos": {"acme": {"verdict": "apply", "verdict_text": "Apply",
                                                            "best_category": "Retail"}}})
            repo.report("2026-10-20-pm", {"ipos": {"acme": {"verdict": "avoid", "verdict_text": "Avoid"}}})
            call = outcomes.call(repo.root, "acme", "2026-10-20")
        self.assertEqual(call["verdict"], "apply")
        self.assertEqual(call["best_category"], "Retail")
        self.assertEqual(call["verdict_report"], "2026-10-20-am.json")
        self.assertEqual(call["anchor_grade"], "strong")

    def test_no_close_date_returns_empty_call(self):
        with TempRepo() as repo:
            call = outcomes.call(repo.root, "acme", None)
        self.assertEqual(call, {
            "verdict": None, "verdict_text": None, "best_category": None,
            "verdict_report": None, "anchor_grade": None,
        })

    def test_no_report_falls_back_to_the_card(self):
        with TempRepo() as repo:
            repo.card("acme", {"anchor_grade": "weak"})
            call = outcomes.call(repo.root, "acme", "2026-10-20")
        self.assertIsNone(call["verdict"])
        self.assertEqual(call["anchor_grade"], "weak")


class ListingPricesTests(NoNetworkCase):
    def row(self, date, series="EQ", open_=110):
        return {"mTIMESTAMP": date, "CH_SERIES": series, "CH_PREVIOUS_CLS_PRICE": "90",
                "CH_OPENING_PRICE": str(open_), "CH_CLOSING_PRICE": "120",
                "CH_TRADE_HIGH_PRICE": "130", "CH_TRADE_LOW_PRICE": "100"}

    def test_picks_the_first_mainboard_row(self):
        nse = FakeNSE({"data": [self.row("22-Oct-2026", open_=115), self.row("21-Oct-2026", open_=110)]})
        result = outcomes.listing_prices(nse, "ACME", "2026-10-21")
        self.assertEqual(result["listed_on"], "2026-10-21")
        self.assertEqual(result["listing"], "110")
        self.assertEqual(result["issue"], "90")
        self.assertEqual(result["source"], "nse")

    def test_filters_non_mainboard_series(self):
        nse = FakeNSE({"data": [self.row("21-Oct-2026", series="SME")]})
        self.assertIsNone(outcomes.listing_prices(nse, "ACME", "2026-10-21"))

    def test_no_rows(self):
        self.assertIsNone(outcomes.listing_prices(FakeNSE({"data": []}), "ACME", "2026-10-21"))


class FinalSubscriptionTests(NoNetworkCase):
    def test_uses_nse_detail(self):
        nse = FakeDetail({"subscription": {"total": {"shares_bid": 5.0, "times": 2.0}}})
        result = outcomes.final_subscription(nse, {"symbol": "ACME"}, {}, "acme")
        self.assertTrue(result["source"].startswith("nse ipo-detail "))
        self.assertEqual(result["data"]["total"]["times"], 2.0)

    def test_falls_back_to_the_snapshot_without_a_symbol(self):
        h = {"sub": {"source": "snapshot x", "data": {}}}
        self.assertEqual(outcomes.final_subscription(None, h, {}, "acme"), h["sub"])

    def test_zero_bids_falls_back(self):
        nse = FakeDetail({"subscription": {"total": {"shares_bid": 0.0, "times": 0.0}}})
        h = {"symbol": "ACME", "sub": {"source": "snapshot x", "data": {}}}
        self.assertEqual(outcomes.final_subscription(nse, h, {}, "acme"), h["sub"])

    def test_error_is_recorded_and_the_snapshot_is_used(self):
        h = {"symbol": "ACME", "sub": {"source": "snapshot x", "data": {}}}
        errors = {}
        result = outcomes.final_subscription(FakeDetail(error=ConnectionError("down")), h, errors, "acme")
        self.assertEqual(result, h["sub"])
        self.assertEqual(errors, {"acme.subscription": "ConnectionError('down')"})


class RecordTests(NoNetworkCase):
    def test_maths(self):
        with TempRepo() as repo:
            row = outcomes.record(repo.root, "acme", history(), prices(), sub())
        self.assertEqual(row["issue_price"], 90.0)
        self.assertEqual(row["listing_price"], 110.0)
        self.assertEqual(row["listing_gain_pct"], 22.22)
        self.assertEqual(row["close_gain_pct"], 33.33)
        self.assertEqual(row["gmp_eve"], 20.0)
        self.assertEqual(row["gmp_eve_pct"], 22.22)
        self.assertEqual(row["gmp_miss_pts"], 0.0)
        self.assertEqual(row["subscription"], {"qib": 3.0, "retail": 2.0, "total": 2.5})

    def test_issue_price_falls_back_to_the_price_high(self):
        p = prices()
        del p["issue"]
        with TempRepo() as repo:
            row = outcomes.record(repo.root, "acme", history(), p, sub())
        self.assertEqual(row["issue_price"], 100.0)

    def test_no_eve_gmp_leaves_gmp_fields_none(self):
        with TempRepo() as repo:
            row = outcomes.record(repo.root, "acme", history(gmps=[]), prices(), sub())
        self.assertIsNone(row["gmp_eve"])
        self.assertIsNone(row["gmp_eve_pct"])
        self.assertIsNone(row["gmp_miss_pts"])


class ScorecardTests(NoNetworkCase):
    def row(self, **fields):
        base = {
            "name": "Acme", "listing_date": "2026-10-21", "verdict": "apply",
            "verdict_text": "Apply", "listing_gain_pct": 20.0, "close_gain_pct": 10.0,
            "gmp_miss_pts": None, "gmp_eve_pct": 18.0, "anchor_grade": "strong",
            "pe": 10.0, "size_cr": 50.0, "subscription": {"total": 2.0, "qib": 3.0, "retail": 2.0, "bnii": 1.0},
        }
        base.update(fields)
        return base

    def test_empty(self):
        self.assertEqual(outcomes.scorecard({}), "# IPO scorecard\n\nNo listings recorded yet.")

    def test_one_listing(self):
        card = outcomes.scorecard({"acme": self.row()})
        self.assertIn("# IPO scorecard — 1 listing", card)
        self.assertIn("| apply | 1 | +20.0% | +10.0% | 1/1 |", card)
        self.assertIn("no GMP recorded the night before any listing yet", card)

    def test_gmp_miss_summary(self):
        card = outcomes.scorecard({"acme": self.row(gmp_miss_pts=2.0)})
        self.assertIn("average miss +2.0 pts", card)

    def test_correlation(self):
        self.assertEqual(outcomes._corr([(1, 1), (2, 2), (3, 3)]), ("+1.00", 3))
        self.assertEqual(outcomes._corr([(1, 1)]), ("–", 1))
        self.assertEqual(outcomes._corr([(1, 5), (2, 5), (3, 5)]), ("–", 3))


class SaveTests(NoNetworkCase):
    def test_saves_ordered_by_listing_date_then_key(self):
        with TempRepo() as repo:
            outcomes.save(repo.root, {
                "b": {"listing_date": "2026-01-02"},
                "a": {"listing_date": "2026-01-01"},
                "c": {"listing_date": "2026-01-01"},
            })
            saved = json.loads((repo.path("data", "outcomes.json")).read_text())
        self.assertEqual(list(saved), ["a", "c", "b"])


class UpdateTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)

    def write_listing(self, key="acme", listing="2026-10-21", symbol="ACME"):
        ipo = {"key": key, "name": "Acme Industries", "listing": listing,
               "open": "2026-10-15", "close": "2026-10-20", "price_high": 100,
               "nse": {"symbol": symbol} if symbol else None}
        self.repo.snapshot("2026-10-15T0907", [ipo])

    def test_records_a_new_listing(self):
        self.write_listing()
        with mock.patch.object(outcomes, "listing_prices", return_value=prices()), \
                mock.patch.object(outcomes, "final_subscription", return_value=sub()):
            new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual((new, waiting, errors), (["acme"], [], {}))
        self.assertEqual(outcomes.load(self.repo.root)["acme"]["listing_price"], 110.0)

    def test_already_recorded_is_skipped(self):
        self.write_listing()
        self.repo.write_json("data/outcomes.json", {"acme": {"listing_date": "2026-10-21"}})
        with mock.patch.object(outcomes, "listing_prices", side_effect=AssertionError("called")):
            new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual((new, waiting, errors), ([], [], {}))

    def test_no_symbol_is_an_error(self):
        self.write_listing(symbol=None)
        new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual(new, [])
        self.assertIn("no NSE symbol", errors["acme"])

    def test_listing_day_without_prices_waits(self):
        self.write_listing(listing=TODAY)
        with mock.patch.object(outcomes, "listing_prices", return_value=None):
            new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual((new, waiting, errors), ([], ["acme"], {}))

    def test_no_prices_three_days_later_is_an_error(self):
        self.write_listing()
        with mock.patch.object(outcomes, "listing_prices", return_value=None):
            new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual(new, [])
        self.assertIn("no NSE prices 3+ days after listing", errors["acme"])

    def test_future_listing_is_skipped(self):
        self.write_listing(listing="2026-11-05")
        new, waiting, errors = outcomes.update(self.repo.root, today=TODAY, client=object())
        self.assertEqual((new, waiting, errors), ([], [], {}))


class SetManualTests(NoNetworkCase):
    def setUp(self):
        super().setUp()
        self.repo = TempRepo()
        self.addCleanup(self.repo.cleanup)
        self.repo.snapshot("2026-10-15T0907", [{
            "key": "acme", "name": "Acme Industries", "listing": "2026-10-21",
            "open": "2026-10-15", "close": "2026-10-20", "price_high": 100,
        }])

    def test_records_manual_prices(self):
        with mock.patch.object(outcomes, "final_subscription", return_value=sub()):
            errors = outcomes.set_manual(self.repo.root, "acme",
                                         ["listing=110", "close=120", "issue=100"], client=object())
        self.assertEqual(errors, {})
        self.assertEqual(outcomes.load(self.repo.root)["acme"]["price_source"], "manual")

    def test_unknown_key_and_missing_listing_price_raise(self):
        with self.assertRaises(SystemExit):
            outcomes.set_manual(self.repo.root, "nope", ["listing=1"], client=object())
        with self.assertRaises(SystemExit):
            outcomes.set_manual(self.repo.root, "acme", ["close=1"], client=object())


class MainNoFetchTests(NoNetworkCase):
    def test_prints_the_saved_scorecard_without_building_a_client(self):
        with TempRepo() as repo:
            saved = {"acme": {
                "name": "Acme", "listing_date": "2026-10-21", "verdict": "apply",
                "verdict_text": "Apply", "listing_gain_pct": 20.0, "close_gain_pct": 10.0,
                "gmp_miss_pts": None, "gmp_eve_pct": 18.0, "anchor_grade": "strong",
                "pe": 10.0, "size_cr": 50.0,
                "subscription": {"total": 2.0, "qib": 3.0, "retail": 2.0, "bnii": 1.0},
            }}
            repo.write_json("data/outcomes.json", saved)
            out = io.StringIO()
            with mock.patch.object(outcomes, "ROOT", repo.root), \
                    mock.patch.object(outcomes, "Client", side_effect=AssertionError("client built")), \
                    redirect_stdout(out):
                code = outcomes.main(["--no-fetch"])
            expected = outcomes.scorecard(saved)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), expected)


if __name__ == "__main__":
    unittest.main()
