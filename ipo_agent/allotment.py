"""Category-wise allotment maths for mainboard IPOs.

Rules used (SEBI ICDR, mainboard book-built issues):
  * Retail (RII): bid up to Rs 2,00,000. When oversubscribed, a lottery gives
    one minimum lot to as many applicants as possible.
  * Small NII (sNII): bid > Rs 2 lakh and <= Rs 10 lakh. Since 2022, allotment
    is a lottery of the *minimum sNII application size*.
  * Big NII (bNII): bid > Rs 10 lakh. Lottery of the minimum bNII size.

Odds are a conservative proxy: 1 / subscription. The real number of
applications is lower than shares_bid / min_size (many bid above the minimum),
so actual odds are usually a bit better.
"""

import math

RETAIL_MAX = 200_000
SNII_MAX = 1_000_000


def min_lots(price, lot):
    """Smallest application (in lots) for each category at the upper band."""
    lot_amt = price * lot
    retail_max = math.floor(RETAIL_MAX / lot_amt)
    return {
        "retail": 1,
        "retail_max": retail_max,
        "snii": retail_max + 1,
        "bnii": math.floor(SNII_MAX / lot_amt) + 1,
    }


def odds(times):
    if times is None:
        return None
    return 1.0 if times <= 1 else 1.0 / times


def categories(price, lot, subscription=None, gmp=None):
    """Return one row per category with capital needed, odds and expected gain."""
    if not price or not lot:
        return []
    lots = min_lots(price, lot)
    sub = subscription or {}
    rows = []
    for key, label in (("retail", "Retail"), ("snii", "Small HNI (sNII)"), ("bnii", "Big HNI (bNII)")):
        n = lots[key]
        amount = n * lot * price
        times = (sub.get(key) or {}).get("times")
        p = odds(times)
        gain_if_allotted = n * lot * gmp if gmp is not None else None
        exp_gain = p * gain_if_allotted if (p is not None and gain_if_allotted is not None) else None
        rows.append(
            {
                "category": key,
                "label": label,
                "min_lots": n,
                "min_shares": n * lot,
                "min_amount": round(amount),
                "subscription_x": times,
                "odds": round(p, 4) if p is not None else None,
                "odds_text": (f"≥1 in {times:.0f}" if times and times > 1 else ("full" if times is not None else "n/a")),
                "gain_if_allotted": round(gain_if_allotted) if gain_if_allotted is not None else None,
                "expected_gain": round(exp_gain) if exp_gain is not None else None,
                "return_on_blocked_pct": round(100 * exp_gain / amount, 2) if exp_gain is not None else None,
            }
        )
    return rows


def best_category(rows):
    """Best = highest expected return per rupee blocked; None if no live data."""
    scored = [r for r in rows if r.get("return_on_blocked_pct") is not None]
    if not scored:
        return None
    return max(scored, key=lambda r: r["return_on_blocked_pct"])["category"]
