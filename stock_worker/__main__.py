"""Dev CLI for the stock fetchers.

``python3 -m stock_worker --dry-run`` prints the planned calls for one symbol
without creating a client; a real run fetches every confirmed source and
prints the records. Records hold ``decimal.Decimal``, which stdlib ``json``
cannot serialise, so the print uses ``default=str``.
"""

import argparse
import json
import sys

from ipo_agent.net import Client

from . import fetchers


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch one symbol's NSE stock records (dev print)."
    )
    parser.add_argument("--symbol", default="RELIANCE")
    parser.add_argument(
        "--since",
        default=None,
        help="announcements: keep rows announced at/after this ISO timestamp",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned calls and exit without any network call",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        for name, url in fetchers.plan_calls(args.symbol):
            print(f"{name}\t{url}")
        return 0

    client = Client(timeout=30, retries=0)
    bundle = fetchers.fetch_all(client, args.symbol, since=args.since)
    print(json.dumps(bundle, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())