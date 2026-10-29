# Test fixtures

All fixtures here are **hand-built** on 2026-10-29 from the response shapes the
parsers read. No live page was captured for this task. Company names, prices,
lots and subscription figures are modelled on
`data/snapshots/2026-10-29T0907.json` where the parser branch allows.

| Fixture | Origin | Modelled on |
| --- | --- | --- |
| `investorgain_gmp.html` | Hand-built, 2026-10-29 | `ipo_agent/investorgain.py:parse` (`self.__next_f.push` chunks and `reportTableData`), with SFC Environmental Technologies values from `data/snapshots/2026-10-29T0907.json`. Acme Industries is deliberately ₹245 × 50 here against ₹250 × 60 on NSE, so the snapshot tests can show NSE's price and lot win |
| `nse_current.json` | Hand-built, 2026-10-29 | `ipo_agent/nse.py:NSE.current` and `parse_detail`; SFC Environmental Technologies and an SME row |
| `nse_upcoming.json` | Hand-built, 2026-10-29 | `ipo_agent/nse.py:NSE.upcoming`; Acme Industries (matches the Investorgain fixture) and Beta Corp (NSE-only) |
| `nse_detail_SFCTECH.json` | Hand-built, 2026-10-29 | `ipo_agent/nse.py:parse_detail` and `parse_subscription`; SFC Environmental Technologies values from `data/snapshots/2026-10-29T0907.json`, including an anchor-report link and a sub-row with no offered quantity |
| `nse_detail_ACME.json` | Hand-built, 2026-10-29 | `ipo_agent/nse.py:parse_detail`; Acme Industries with zero bids and no RHP link (to exercise the SEBI fallback) |
| `nse_detail_BETA.json` | Hand-built, 2026-10-29 | `ipo_agent/nse.py:parse_detail`; Beta Corp, NSE-only |
| `sebi_listing.html` | Hand-built, 2026-10-29 | `ipo_agent/sebi.py:listing`; one normal row, one corrigendum, one addendum and one row with no filing link |
| `sebi_rhp_page.html` | Hand-built, 2026-10-29 | `ipo_agent/sebi.py:pdf_url`; the `file=<pdf>` link shape |
| `sebi_rhp_page_generic.html` | Hand-built, 2026-10-29 | `ipo_agent/sebi.py:pdf_url`; a bare `attachdocs/*.pdf` link |

If a real captured page replaces one of these, add a row or change the Origin
cell to **Captured** with the source URL and capture date.
