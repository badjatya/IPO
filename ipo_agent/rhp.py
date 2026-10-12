"""Download an RHP from NSE archives and extract the sections that matter for
an IPO review into a compact text file (~35k tokens instead of ~600k).

Usage:
    python3 -m ipo_agent.rhp <SYMBOL|zip-or-pdf-url> [--out analysis/rhp/<name>.txt]

Needs `pdftotext` (poppler-utils). Falls back to `pypdf` if installed.
"""

import argparse
import io
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .net import Client

ROOT = pathlib.Path(__file__).resolve().parent.parent

# (heading as printed in RHP, max chars to keep, alternative wordings)
WANTED = [
    ("THE OFFER", 6000, []),
    ("SUMMARY OF RESTATED FINANCIAL INFORMATION", 14000,
     ["SUMMARY FINANCIAL INFORMATION", "SUMMARY OF FINANCIAL INFORMATION",
      "SUMMARY OF RESTATED CONSOLIDATED FINANCIAL INFORMATION", "SUMMARY RESTATED FINANCIAL INFORMATION"]),
    ("CAPITAL STRUCTURE", 12000, []),
    ("OBJECTS OF THE OFFER", 12000, ["OBJECTS OF THE ISSUE"]),
    ("BASIS OF OFFER PRICE", 25000, ["BASIS FOR OFFER PRICE", "BASIS FOR THE OFFER PRICE", "BASIS OF THE OFFER PRICE"]),
    ("OUR BUSINESS", 22000, []),
    ("OUR PROMOTERS AND PROMOTER GROUP", 8000, ["OUR PROMOTER AND PROMOTER GROUP"]),
    ("RISK FACTORS", 15000, []),
    ("MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF", 12000,
     ["MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS",
      "MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL POSITION AND RESULTS OF OPERATIONS",
      "MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL POSITION AND RESULTS OF"]),
    ("OUTSTANDING LITIGATION AND MATERIAL DEVELOPMENTS", 6000, []),
    ("OFFER STRUCTURE", 7000, ["ISSUE STRUCTURE"]),  # QIB / NII / retail % split
]


def _key(s):
    s = s.upper().replace("'", "’")
    s = re.sub(r"^SECTION [IVX]+\s*[:–—-]\s*", "", s.strip())
    return re.sub(r"\s+", " ", s)


def pdf_to_text(pdf_path):
    if shutil.which("pdftotext"):
        return subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True, capture_output=True,
        ).stdout.decode("utf-8", errors="replace")
    from pypdf import PdfReader  # pip install pypdf

    return "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf_path)).pages)


def toc_headings(lines):
    """Section names from the table of contents (lines ending in dot leaders)."""
    heads = []
    for ln in lines[:600]:
        m = re.match(r"^\s*(.+?)\s*\.{5,}\s*\d*\s*$", ln)
        if m and " " in _key(m.group(1)):  # skip one-word tails of wrapped entries ("OPERATIONS")
            heads.append(_key(m.group(1)))
    return heads


def split_sections(text):
    lines = text.splitlines()
    heads = set(toc_headings(lines)) | {_key(h) for h, _, alts in WANTED for h in [h, *alts]}
    toc_end = next((i for i, ln in enumerate(lines) if "SECTION I" in ln and "...." not in ln), 0)
    starts = []
    for i in range(toc_end, len(lines)):
        k = _key(lines[i])
        if k in heads and (not starts or starts[-1][1] != k):
            if starts and i - starts[-1][0] <= 3:
                starts.pop()  # "SECTION VI – ..." banner directly followed by its first heading
            starts.append((i, k))
    sections = {}
    for n, (i, k) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        sections.setdefault(k, "\n".join(lines[i:end]))
    return sections


def compact(s):
    s = re.sub(r"[ \t]{3,}", "  ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def extract(text):
    secs = split_sections(text)
    out = []
    for head, cap, alts in WANTED:
        body = next((secs[_key(h)] for h in [head, *alts] if _key(h) in secs), None)
        if not body:
            out.append(f"\n===== {head} =====\n[not found]\n")
            continue
        body = compact(body)
        clipped = " [...truncated]" if len(body) > cap else ""
        out.append(f"\n===== {head} =====\n{body[:cap]}{clipped}\n")
    return "".join(out)


def fetch_rhp_pdf(src, workdir):
    url = src if src.startswith("http") else f"https://nsearchives.nseindia.com/content/ipo/RHP_{src}.zip"
    data = Client(timeout=120).get(url)
    target = pathlib.Path(workdir) / "rhp.pdf"
    if data[:4] == b"%PDF":  # direct PDF link (e.g. SEBI / BSE / company site)
        target.write_bytes(data)
        return target
    z = zipfile.ZipFile(io.BytesIO(data))
    pdfs = sorted((n for n in z.namelist() if n.lower().endswith(".pdf")),
                  key=lambda n: z.getinfo(n).file_size, reverse=True)
    if not pdfs:
        raise ValueError(f"no PDF in {url}")
    target.write_bytes(z.read(pdfs[0]))  # largest PDF = the RHP itself
    return target


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="NSE symbol (e.g. HDFIRE), or an RHP .zip/.pdf URL")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    name = args.src if not args.src.startswith("http") else re.sub(r"\W+", "_", args.src)[-40:]
    out = pathlib.Path(args.out) if args.out else ROOT / "analysis" / "rhp" / f"{name}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        text = pdf_to_text(fetch_rhp_pdf(args.src, tmp))
    out.write_text(extract(text))
    print(f"wrote {out} ({out.stat().st_size // 1000} KB)")


if __name__ == "__main__":
    sys.exit(main())
