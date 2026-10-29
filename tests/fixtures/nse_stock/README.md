# NSE stock smoke fixtures

Captured by: local
Captured at: 2026-10-29T11:46:08+00:00

Top-level JSON lists keep the first 20 rows; the equity CSV is saved in full. Do not trim a fixture by hand.

| Endpoint | Fixture | Rows | Bytes (original / saved) | Unit |
| --- | --- | --- | --- | --- |
| `results_standalone` | `results_standalone.json` | 5 | 14525 / 17588 | unit not stated |
| `results_consolidated` | `results_consolidated.json` | 5 | 14525 / 17588 | unit not stated |
| `results_filings` | `results_filings.json` | 130 | 101760 / 18529 | unit not stated |
| `announcements` | `announcements.json` | 3374 | 2910087 / 17530 | unit not stated |
| `announcements_market` | `announcements_market.json` | 3484 | 2432858 / 16168 | unit not stated |
| `shareholding` | `shareholding.json` | 23 | 43031 / 35779 | unit not stated |
| `pledges` | `pledges.json` | 1 | 670 / 869 | unit not stated |
| `pledges_market` | `pledges_market.json` | 1558 | 972529 / 16037 | unit not stated |
| `equity_list` | `equity_list.csv` | 2620 | 185023 / 185023 | unit not stated |

## Field coverage

### `results_standalone`
- period_end: found (`resCmpData[].re_to_dt`)
- revenue: found (`resCmpData[].re_net_sale`)
- other_income: found (`resCmpData[].re_oth_inc_new`)
- expenses: found (`resCmpData[].re_oth_tot_exp`)
- net_profit: found (`resCmpData[].re_net_profit`)
- eps: found (`resCmpData[].re_basic_eps_for_cont_dic_opr`)
- ebitda: not in this response (`resCmpData[].re_ebitda`)
- filing_link: not in this response (`resCmpData[].re_filing_link`)

### `results_consolidated`
- period_end: found (`resCmpData[].re_to_dt`)
- revenue: found (`resCmpData[].re_net_sale`)
- other_income: found (`resCmpData[].re_oth_inc_new`)
- expenses: found (`resCmpData[].re_oth_tot_exp`)
- net_profit: found (`resCmpData[].re_net_profit`)
- eps: found (`resCmpData[].re_basic_eps_for_cont_dic_opr`)
- ebitda: not in this response (`resCmpData[].re_ebitda`)
- filing_link: not in this response (`resCmpData[].re_filing_link`)

### `results_filings`
- period_start: found (`[].fromDate`)
- period_end: found (`[].toDate`)
- consolidated: found (`[].consolidated`)
- audited: found (`[].audited`)
- filed_at: found (`[].filingDate`)
- xbrl_link: found (`[].xbrl`)
- details_link: not in this response (`[].resultDetailedDataLink`)

### `announcements`
- symbol: found (`[].symbol`)
- subject: found (`[].desc`)
- announced_at: found (`[].an_dt`)
- title: found (`[].attchmntText`)
- attachment: found (`[].attchmntFile`)
- exchange_ref: found (`[].seq_id`)
- industry: found (`[].smIndustry`)

### `announcements_market`
- symbol: found (`[].symbol`)
- subject: found (`[].desc`)
- announced_at: found (`[].an_dt`)
- title: found (`[].attchmntText`)
- attachment: found (`[].attchmntFile`)
- exchange_ref: found (`[].seq_id`)
- industry: found (`[].smIndustry`)

### `shareholding`
- as_on: found (`[].date`)
- submitted_at: found (`[].submissionDate`)
- promoter: found (`[].pr_and_prgrp`)
- public: found (`[].public_val`)
- employee_trusts: found (`[].employeeTrusts`)
- fii: not in this response (`[].fii`)
- dii: not in this response (`[].dii`)
- xbrl_link: found (`[].xbrl`)

### `pledges`
- symbol: not in this response (`data[].symbol`)
- company: found (`data[].comName`)
- shares_held: found (`data[].totPromoterHolding`)
- shares_pledged: found (`data[].numSharesPledged`)
- pledged_pct: found (`data[].percSharesPledged`)
- promoter_pct: found (`data[].percPromoterHolding`)
- promoter_pledged_pct: found (`data[].percPromoterShares`)
- quarter_end: found (`data[].shp`)
- disclosed_at: found (`data[].broadcastDt`)

### `pledges_market`
- symbol: not in this response (`data[].symbol`)
- company: found (`data[].comName`)
- shares_held: found (`data[].totPromoterHolding`)
- shares_pledged: found (`data[].numSharesPledged`)
- pledged_pct: found (`data[].percSharesPledged`)
- promoter_pct: found (`data[].percPromoterHolding`)
- promoter_pledged_pct: found (`data[].percPromoterShares`)
- quarter_end: found (`data[].shp`)
- disclosed_at: found (`data[].broadcastDt`)

### `equity_list`
- SYMBOL: found (`SYMBOL`)
- NAME OF COMPANY: found (`NAME OF COMPANY`)
- SERIES: found (`SERIES`)
- DATE OF LISTING: found (`DATE OF LISTING`)
- PAID UP VALUE: found (`PAID UP VALUE`)
- MARKET LOT: found (`MARKET LOT`)
- ISIN NUMBER: found (`ISIN NUMBER`)
- FACE VALUE: found (`FACE VALUE`)
