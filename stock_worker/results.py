"""Quarterly results: ``results-comparision`` rows joined with the
``corporates-financial-results`` filings rows.

Records are keyed exactly as the ``db.md`` ``quarterly_results`` columns:

``period_end``               ISO date (``re_to_dt``) — the natural key
``consolidated``             always ``False``: the comparison rows are standalone
                             and the endpoint ignores ``consolidated=true``
``revenue_cr``               ``re_net_sale`` (₹ lakh → crore; ``None`` when
                             net sale is absent — ``re_total_inc`` includes
                             other income, which is its own column)
``other_income_cr``          ``re_oth_inc_new`` (fallback ``re_oth_inc``)
``expenses_cr``              ``re_oth_tot_exp``
``ebitda_cr``                operating EBITDA, excluding other income —
                             revenue − (total expenses − finance costs −
                             depreciation) from ``re_net_sale``,
                             ``re_oth_tot_exp``, ``re_int_new``,
                             ``re_depr_und_exp``, all four stated or ``None``
``pat_cr``                   ``re_net_profit`` (fallback ``re_proloss_ord_act``)
``eps``                      ``re_basic_eps_for_cont_dic_opr``, ₹ per share,
                             never converted
``filed_at`` / ``source_url``  only from the filings row with the same
                             ``toDate`` and ``consolidated == "Non-Consolidated"``
                             (``filingDate`` / ``broadCastDate``, and the
                             ``xbrl`` link); both ``None`` without such a row

Extras (no db.md column; listed here as the plan requires): ``period_start``
(``re_from_dt``) and ``audited`` (the matched filings row's ``audited``).

Amounts from ``results-comparision`` are ₹ lakh: RELIANCE's own note text on
the first fixture row ("Net Revenue is Rs 128,260 crore") matches
``re_net_sale`` 12,826,000 lakh, so the parser converts every amount with
``util.to_crore`` (÷100). Missing fields are ``None``, never estimated; a
stated ``0`` is a value. ``consolidated=True`` requests return no rows and a
gap flag (``parse_consolidated``), never standalone figures relabelled.
"""

from .util import parse_date, parse_timestamp, to_crore, to_decimal

CONSOLIDATED_GAP = (
    "results-comparision ignores consolidated=true and returns the standalone "
    "body; no consolidated source is confirmed (recorded in data-sources.md, "
    "re-checked once by stock_worker.probe). Do not infer consolidated numbers "
    "from standalone."
)

EBITDA_FIELDS = ("re_net_sale", "re_oth_tot_exp", "re_int_new", "re_depr_und_exp")


def _rows(body):
    """The comparison/filings response is a dict with a list, or a plain list."""
    if isinstance(body, dict):
        return body.get("resCmpData") or []
    return body or []


def _first(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _ebitda(row):
    """Operating EBITDA, excluding other income, only from stated fields."""
    values = [_first(row, name) for name in EBITDA_FIELDS]
    if any(value is None for value in values):
        return None
    revenue, expenses, finance, depreciation = (to_decimal(value) for value in values)
    if None in (revenue, expenses, finance, depreciation):
        return None
    return to_crore(revenue - (expenses - finance - depreciation))


def parse_results(comparison, filings):
    """Standalone records from the comparison body, joined with the filings.

    ``filings`` is the ``corporates-financial-results`` response (a list of
    rows). ``filed_at``/``source_url``/``audited`` come only from the
    ``Non-Consolidated`` filings row with the same ``toDate``.
    """
    filing_by_end = {}
    for row in filings or []:
        end = parse_date(row.get("toDate"))
        if (
            end is not None
            and row.get("consolidated") == "Non-Consolidated"
            and end not in filing_by_end
        ):
            filing_by_end[end] = row

    records = []
    for row in _rows(comparison):
        period_end = parse_date(row.get("re_to_dt"))
        filing = filing_by_end.get(period_end) if period_end else None
        filed_at = None
        source_url = None
        audited = None
        if filing is not None:
            filed_at = parse_timestamp(_first(filing, "filingDate", "broadCastDate"))
            source_url = filing.get("xbrl")
            audited = filing.get("audited")
        records.append(
            {
                "period_end": period_end,
                "consolidated": False,
                "revenue_cr": to_crore(to_decimal(row.get("re_net_sale"))),
                "other_income_cr": to_crore(
                    to_decimal(_first(row, "re_oth_inc_new", "re_oth_inc"))
                ),
                "expenses_cr": to_crore(to_decimal(row.get("re_oth_tot_exp"))),
                "ebitda_cr": _ebitda(row),
                "pat_cr": to_crore(
                    to_decimal(_first(row, "re_net_profit", "re_proloss_ord_act"))
                ),
                "eps": to_decimal(row.get("re_basic_eps_for_cont_dic_opr")),
                "filed_at": filed_at,
                "source_url": source_url,
                "period_start": parse_date(row.get("re_from_dt")),
                "audited": audited,
            }
        )
    return records


def parse_consolidated(comparison):
    """No consolidated rows: the endpoint's ``consolidated=true`` answer was
    byte-identical to standalone in 003 and the probe re-checks it once.

    Returns ``(records, gap)`` — always no records and a gap flag for the
    recorded gap; standalone figures are never relabelled consolidated.
    """
    return [], {"consolidated": CONSOLIDATED_GAP}