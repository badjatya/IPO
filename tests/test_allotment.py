import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from support import NoNetworkCase  # noqa: E402

from ipo_agent import allotment  # noqa: E402


class MinLotsTests(NoNetworkCase):
    def test_standard_price_and_lot(self):
        self.assertEqual(
            allotment.min_lots(100, 10),
            {"retail": 1, "retail_max": 200, "snii": 201, "bnii": 1001},
        )

    def test_retail_max_boundary_is_inclusive(self):
        # ₹2,000 x 10 = ₹20,000, so ₹2 L buys exactly 10 lots.
        self.assertEqual(allotment.min_lots(2000, 10)["retail_max"], 10)
        # ₹2,001 x 10 = ₹20,010: only 9 full lots fit under the ₹2 L cap.
        self.assertEqual(allotment.min_lots(2001, 10)["retail_max"], 9)

    def test_one_lot_cost_above_retail_cap_still_gives_one_lot(self):
        lots = allotment.min_lots(1000, 250)
        self.assertEqual(lots["retail"], 1)
        self.assertEqual(lots["retail_max"], 0)
        self.assertEqual(lots["snii"], 1)
        self.assertEqual(lots["bnii"], 5)

    def test_bnii_boundary(self):
        # ₹1,000 x 10 = ₹10,000; the ₹10 L cap buys exactly 100 lots, so bNII is 101.
        self.assertEqual(allotment.min_lots(1000, 10)["bnii"], 101)


class OddsTests(NoNetworkCase):
    def test_none(self):
        self.assertIsNone(allotment.odds(None))

    def test_at_or_below_one_is_full(self):
        for times in (0, 0.5, 1, 1.0):
            self.assertEqual(allotment.odds(times), 1.0)

    def test_above_one_is_inverse(self):
        self.assertEqual(allotment.odds(2), 0.5)
        self.assertEqual(allotment.odds(4), 0.25)
        self.assertAlmostEqual(allotment.odds(3), 1 / 3)


class CategoriesTests(NoNetworkCase):
    def test_no_price_or_lot_returns_no_rows(self):
        self.assertEqual(allotment.categories(None, 10), [])
        self.assertEqual(allotment.categories(100, None), [])
        self.assertEqual(allotment.categories(0, 10), [])

    def test_rows_without_subscription_or_gmp(self):
        rows = allotment.categories(100, 10)
        self.assertEqual([r["category"] for r in rows], ["retail", "snii", "bnii"])
        self.assertEqual(rows[0]["min_lots"], 1)
        self.assertEqual(rows[0]["min_shares"], 10)
        self.assertEqual(rows[0]["min_amount"], 1000)
        self.assertIsNone(rows[0]["subscription_x"])
        self.assertIsNone(rows[0]["odds"])
        self.assertEqual(rows[0]["odds_text"], "n/a")
        self.assertIsNone(rows[0]["gain_if_allotted"])
        self.assertIsNone(rows[0]["expected_gain"])
        self.assertIsNone(rows[0]["return_on_blocked_pct"])

    def test_rows_with_subscription_and_gmp(self):
        sub = {"retail": {"times": 2}, "snii": {"times": 0.5}, "bnii": {"times": 5}}
        rows = {r["category"]: r for r in allotment.categories(100, 10, sub, gmp=20)}
        retail = rows["retail"]
        self.assertEqual(retail["subscription_x"], 2)
        self.assertEqual(retail["odds"], 0.5)
        self.assertEqual(retail["odds_text"], "≥1 in 2")
        self.assertEqual(retail["gain_if_allotted"], 200)
        self.assertEqual(retail["expected_gain"], 100)
        self.assertEqual(retail["return_on_blocked_pct"], 10.0)
        self.assertEqual(rows["snii"]["odds_text"], "full")
        self.assertEqual(rows["bnii"]["odds"], 0.2)

    def test_rounding_of_amount_and_gains(self):
        rows = allotment.categories(333, 45, {"retail": {"times": 3}}, gmp=7)
        retail = rows[0]
        self.assertEqual(retail["min_amount"], round(333 * 45))
        self.assertEqual(retail["gain_if_allotted"], round(1 * 45 * 7))
        self.assertEqual(retail["expected_gain"], round((1 / 3) * 45 * 7))
        self.assertEqual(retail["return_on_blocked_pct"], 0.7)


class BestCategoryTests(NoNetworkCase):
    def test_picks_highest_return_on_blocked(self):
        rows = [
            {"category": "retail", "return_on_blocked_pct": 4.0},
            {"category": "snii", "return_on_blocked_pct": 9.5},
            {"category": "bnii", "return_on_blocked_pct": None},
        ]
        self.assertEqual(allotment.best_category(rows), "snii")

    def test_none_when_no_live_data(self):
        self.assertIsNone(allotment.best_category([]))
        self.assertIsNone(
            allotment.best_category([{"category": "retail", "return_on_blocked_pct": None}])
        )


if __name__ == "__main__":
    unittest.main()
