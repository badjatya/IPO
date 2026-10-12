"""SEBI 'Red Herring Documents filed with ROC' listing: finds the RHP PDF for an
IPO before NSE publishes its issue page (usually 2-5 days before opening).
"""

import html
import re

LIST_URL = ("https://www.sebi.gov.in/sebiweb/home/HomeAction.do"
            "?doListing=yes&sid=3&ssid=15&smid=11")


def listing(client):
    """[(date, title, page_url)] newest first, RHP entries only."""
    page = client.get_text(LIST_URL, accept="text/html")
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        href = re.search(r"href=['\"]([^'\"]+/filings/public-issues/[^'\"]+)", row)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", row))).strip()
        if not href:
            continue
        m = re.match(r"([A-Z][a-z]{2} \d{2}, \d{4})\s+(.*)", text)
        title = (m.group(2) if m else text).split(" - ")[0].split(" – ")[0]
        title = re.sub(r'"\s*class="points">.*', "", title).strip()
        url = href.group(1)
        if "corrigendum" in url or "addendum" in url:
            continue
        out.append((m.group(1) if m else "", title, url))
    return out


def pdf_url(client, page_url):
    page = client.get_text(page_url, accept="text/html")
    m = re.search(r"file=(https://www\.sebi\.gov\.in/sebi_data/attachdocs/[^'\"&]+\.pdf)", page)
    if not m:
        m = re.search(r"(https://www\.sebi\.gov\.in/sebi_data/attachdocs/[^'\"&]+\.pdf)", page)
    return m.group(1) if m else None
