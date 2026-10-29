import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from support import NoNetworkCase  # noqa: E402

from stock_worker import announcements  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "nse_stock"
KEYS = {
    "symbol", "subject", "announced_at", "title", "attachment_url",
    "exchange_ref", "industry",
}


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class AnnouncementsTests(NoNetworkCase):
    def test_fixture_parses_to_20_records_with_the_documented_fields(self):
        records = announcements.parse(load("announcements.json"))
        self.assertEqual(len(records), 20)
        for record in records:
            self.assertEqual(set(record), KEYS)
        first = records[0]
        self.assertEqual(first["symbol"], "RELIANCE")
        self.assertEqual(first["subject"], "Other Restructuring")
        self.assertEqual(first["announced_at"], "2026-10-29T08:55:40+05:30")
        self.assertEqual(
            first["title"],
            "Disclosure under Regulation 30 of the Securities and Exchange Board "
            "of India (Listing Obligations and Disclosure Requirements) "
            "Regulations, 2015   Voluntary strike off of Hamleys (Franchising) "
            "Limited",
        )
        self.assertEqual(
            first["attachment_url"],
            "https://nsearchives.nseindia.com/corporate/"
            "kavinavora_29102026084603_SE_29102026.pdf",
        )
        self.assertEqual(first["exchange_ref"], "106833561")
        self.assertEqual(first["industry"], "Refineries")

    def test_since_keeps_only_newer_rows(self):
        records = announcements.parse(
            load("announcements.json"), since="2026-10-25T00:00:00+05:30"
        )
        self.assertEqual(len(records), 3)
        for record in records:
            self.assertGreaterEqual(
                record["announced_at"], "2026-10-25T00:00:00+05:30"
            )
        self.assertEqual(records[0]["exchange_ref"], "106833561")
        self.assertEqual(records[-1]["exchange_ref"], "106830931")

    def test_since_matching_the_latest_row_keeps_it(self):
        records = announcements.parse(
            load("announcements.json"), since="2026-10-29T08:55:40+05:30"
        )
        self.assertEqual([r["exchange_ref"] for r in records], ["106833561"])

    def test_utc_since_drops_an_older_ist_row_and_keeps_a_newer_one(self):
        # 2026-10-29T05:00:00+00:00 is 10:30 IST. The 08:55 IST row (03:25 UTC)
        # is older and is dropped; the 11:12 IST row (05:42 UTC) is newer.
        rows = [
            {"an_dt": "29-Oct-2026 08:55:40", "desc": "old", "seq_id": "1"},
            {"an_dt": "29-Oct-2026 11:12:00", "desc": "new", "seq_id": "2"},
        ]
        records = announcements.parse(rows, since="2026-10-29T05:00:00+00:00")
        self.assertEqual([r["exchange_ref"] for r in records], ["2"])

    def test_utc_since_boundary_equal_time_is_kept(self):
        # 08:55:40 IST == 03:25:40 UTC; strictly-before drops, equal keeps.
        rows = [{"an_dt": "29-Oct-2026 08:55:40", "desc": "x", "seq_id": "1"}]
        records = announcements.parse(rows, since="2026-10-29T03:25:40+00:00")
        self.assertEqual([r["exchange_ref"] for r in records], ["1"])

    def test_naive_since_is_read_as_ist(self):
        rows = [
            {"an_dt": "29-Oct-2026 10:00:00", "desc": "x", "seq_id": "1"},
            {"an_dt": "29-Oct-2026 11:30:00", "desc": "y", "seq_id": "2"},
        ]
        records = announcements.parse(rows, since="2026-10-29T10:30:00")
        self.assertEqual([r["exchange_ref"] for r in records], ["2"])

    def test_date_only_since_is_midnight_ist(self):
        rows = [
            {"an_dt": "25-Oct-2026 23:00:00", "desc": "x", "seq_id": "1"},
            {"an_dt": "26-Oct-2026 00:30:00", "desc": "y", "seq_id": "2"},
        ]
        records = announcements.parse(rows, since="2026-10-26")
        self.assertEqual([r["exchange_ref"] for r in records], ["2"])

    def test_junk_since_raises_value_error(self):
        with self.assertRaises(ValueError):
            announcements.parse([], since="not-a-timestamp")

    def test_row_without_a_timestamp_is_kept_under_since(self):
        # A row with no usable announced_at cannot be proven older; it is kept
        # (the caller dedupes by exchange_ref).
        records = announcements.parse(
            [{"seq_id": "1", "desc": "x"}], since="2026-10-29T05:00:00+00:00"
        )
        self.assertEqual(len(records), 1)

    def test_no_since_keeps_every_parsed_row(self):
        # Without a since filter all 20 rows stay (oldest: 21-Sep-2026 19:05).
        self.assertEqual(len(announcements.parse(load("announcements.json"))), 20)

    def test_market_fixture_parses_with_the_same_paths(self):
        records = announcements.parse(load("announcements_market.json"))
        self.assertEqual(len(records), 20)
        self.assertIn("symbol", records[0])
        self.assertIsNotNone(records[0]["symbol"])
        self.assertIsNotNone(records[0]["announced_at"])

    def test_row_without_attachment_gives_none(self):
        row = {
            "an_dt": "29-Oct-2026 08:55:40",
            "desc": "Updates",
            "attchmntText": "No file",
            "seq_id": "1",
            "smIndustry": "Refineries",
            "symbol": "RELIANCE",
        }
        record = announcements.parse([row])[0]
        self.assertIsNone(record["attachment_url"])

    def test_missing_announced_at_is_none_not_dropped(self):
        record = announcements.parse([{"seq_id": "1", "desc": "x"}])[0]
        self.assertIsNone(record["announced_at"])
        self.assertIsNone(record["attachment_url"])
        self.assertIsNone(record["industry"])

    def test_empty_response_is_empty(self):
        self.assertEqual(announcements.parse([]), [])
        self.assertEqual(announcements.parse({"data": []}), [])


if __name__ == "__main__":
    unittest.main()