#!/usr/bin/env python3
"""Fetch OA PDFs for shortlisted papers; emit a manual-fetch HTML for the rest.

Reads scopus_out10/stage_shortlists.md, queries Unpaywall for each DOI, and:
  - downloads an open-access PDF to scopus_out10/papers_oa/ when available
  - emits scopus_out10/papers_manual.html with clickable DOI links for the
    paywalled remainder (open in a VPN'd browser)
  - writes a CSV log of per-paper status

Unpaywall is free, legal, and doesn't require authentication.
"""
import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

EMAIL = "ignacio.chechile@gmail.com"  # Unpaywall polite-pool identifier
USER_AGENT = f"SLR-pipeline/1.0 (mailto:{EMAIL})"
DELAY = 0.15  # ~7 req/s, well under Unpaywall's 100k/day limit

ELSEVIER_CONFIG = Path(__file__).resolve().parent.parent.parent / "config.json"


# ── Markdown parsing ───────────────────────────────────────────────────────

ROW_RE = re.compile(r"^\|(.+)\|$")
DOI_RE = re.compile(r"\[([^\]]+)\]\(")


def extract_rows_from_md(md_path):
    rows = []
    current_stage = None
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_stage = line[3:].split(" (")[0].strip()
            continue
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Role"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        # Support both 8-column (pre-gist) and 9-column (with Gist) formats
        if len(parts) == 9:
            role, year, author, method, task, cites, title, _gist, doi_cell = parts
        elif len(parts) >= 8:
            role, year, author, method, task, cites, title, doi_cell = parts[:8]
        else:
            continue
        m = DOI_RE.search(doi_cell)
        doi = m.group(1) if m else ""
        if doi == "—":
            doi = ""
        rows.append({
            "stage": current_stage, "role": role, "year": year, "author": author,
            "method": method, "task": task, "cites": cites,
            "title": title, "doi": doi,
        })
    return rows


# ── Unpaywall lookup + PDF fetch ───────────────────────────────────────────

def unpaywall_lookup(doi):
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi, safe='/')}?email={urllib.parse.quote(EMAIL)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as ex:
        return {"_error": str(ex)[:120]}


# ── Abstracts: OpenAlex (primary) + Elsevier (fallback) ───────────────────

def _reconstruct_inverted(inv):
    positions = []
    for word, ps in inv.items():
        for p in ps:
            positions.append((p, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def openalex_abstract(doi):
    url = (f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/')}"
           f"?mailto={urllib.parse.quote(EMAIL)}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    inv = data.get("abstract_inverted_index")
    if not inv:
        return None
    return _reconstruct_inverted(inv).strip() or None


def elsevier_abstract(doi, api_key):
    url = f"https://api.elsevier.com/content/abstract/doi/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    try:
        desc = data["abstracts-retrieval-response"]["coredata"]["dc:description"]
    except (KeyError, TypeError):
        return None
    if not desc:
        return None
    if isinstance(desc, dict):
        desc = " ".join(str(v) for v in desc.values() if v)
    return desc.strip() or None


def sciencedirect_article_abstract(doi, api_key):
    """Fallback: ScienceDirect Article Retrieval API. Works for Elsevier-
    published journals (Microelectronics Journal, Microelectronics Reliability,
    Integration / VLSI Journal, J. Industrial Info Integration). Different
    endpoint from content/abstract — and the default view returns dc:description
    even for keys that can't access FULL-view abstracts."""
    url = f"https://api.elsevier.com/content/article/doi/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    root = data.get("full-text-retrieval-response", data)
    try:
        desc = root["coredata"]["dc:description"]
    except (KeyError, TypeError):
        return None
    if not desc:
        return None
    if isinstance(desc, dict):
        desc = " ".join(str(v) for v in desc.values() if v)
    return desc.strip() or None


_BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def scrape_doi_page(doi):
    """Follow DOI redirect and extract abstract from publisher meta tags.
    Works for IEEE Xplore, ACM DL, Springer, many others. ScienceDirect
    blocks naked requests (403) and returns None."""
    url = f"https://doi.org/{urllib.parse.quote(doi, safe='/')}"
    req = urllib.request.Request(url, headers={
        "User-Agent": _BROWSER_UA,
        "Accept-Language": "en-US,en",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    for pat in [
        r'<meta\s+name=[\'"]citation_abstract[\'"][^>]*content=[\'"](.*?)[\'"]',
        r'<meta\s+property=[\'"]og:description[\'"][^>]*content=[\'"](.*?)[\'"]',
        r'<meta\s+name=[\'"]description[\'"][^>]*content=[\'"](.*?)[\'"]',
    ]:
        m = re.search(pat, page, re.DOTALL | re.IGNORECASE)
        if m and len(m.group(1)) > 100:
            return html.unescape(m.group(1)).strip()
    return None


def fetch_abstract(doi, cache, els_key=None):
    """Returns (abstract, source) using cache; (None, None) if unavailable.
    Fallback chain: OpenAlex → Elsevier Abstract API → ScienceDirect Article
    API → publisher-page scrape."""
    key = doi.lower()
    if key in cache:
        c = cache[key]
        return c.get("abstract"), c.get("source")
    abs_text = openalex_abstract(doi)
    src = "openalex" if abs_text else None
    if not abs_text and els_key:
        abs_text = elsevier_abstract(doi, els_key)
        src = "elsevier_abstract_api" if abs_text else None
    if not abs_text and els_key:
        abs_text = sciencedirect_article_abstract(doi, els_key)
        src = "elsevier_article_api" if abs_text else None
    if not abs_text:
        abs_text = scrape_doi_page(doi)
        src = "publisher_meta" if abs_text else None
    cache[key] = {"abstract": abs_text, "source": src}
    return abs_text, src


def slugify(s, maxlen=45):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip()).strip("_")
    return s[:maxlen].rstrip("_") or "untitled"


def first_author_lastname(full):
    if not full:
        return "Unknown"
    return re.split(r"[ ,]", full.strip())[0] or "Unknown"


def download_pdf(url, dest_path):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except Exception as ex:
        return False, f"fetch_error_{str(ex)[:80]}"
    if data[:4] != b"%PDF":
        return False, f"not_pdf_ctype={ctype[:40]}"
    dest_path.write_bytes(data)
    return True, f"ok_{len(data)}B"


# ── Manual-fetch HTML ──────────────────────────────────────────────────────

HTML_HEAD = """<!doctype html>
<html><head><meta charset="utf-8"><title>Manual Fetch — AI for Chips shortlist</title>
<style>
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;max-width:900px;margin:2em auto;padding:0 1em;color:#222}
h1{font-size:1.5em}h2{border-bottom:1px solid #ddd;padding-bottom:.2em;margin-top:2em}
.paper{margin:.8em 0;padding:.6em .8em;border-left:3px solid #0072B2;background:#f7f7f9}
.meta{color:#666;font-size:.9em}
.title{font-weight:600;display:block;margin-bottom:.2em}
a{color:#0072B2;text-decoration:none}a:hover{text-decoration:underline}
.tag{display:inline-block;padding:1px 6px;margin-right:.3em;border-radius:3px;background:#e0e0e8;font-size:.8em;color:#444}
.instructions{background:#fff8e1;border-left:3px solid #e69f00;padding:.8em 1em;margin:1em 0}
details{margin-top:.5em}
details>summary{cursor:pointer;color:#0072B2;font-size:.9em;user-select:none}
details>summary:hover{text-decoration:underline}
.abstract{margin-top:.4em;padding:.5em .7em;background:#fff;border:1px solid #e0e0e8;border-radius:3px;color:#333;font-size:.95em;line-height:1.5}
.abs-missing{color:#999;font-style:italic;font-size:.85em;margin-top:.3em}
.src-tag{font-size:.75em;color:#999;margin-left:.4em}
</style></head><body>
<h1>Manual fetch list — papers not available via Unpaywall</h1>
<div class="instructions">
Open this page in a browser <b>authenticated via your university VPN / institutional proxy</b>.
Click each DOI link — it will resolve to the publisher (IEEE Xplore, ACM DL, Elsevier…) through your institution's access.
Expand the <b>Abstract</b> toggle under each paper to triage before opening.
</div>
"""

HTML_FOOT = "</body></html>\n"


def build_manual_html(rows, out_path, summary, abstracts):
    parts = [HTML_HEAD]
    parts.append(f"<p class='meta'>{summary}</p>")
    by_stage = defaultdict(list)
    for r in rows:
        by_stage[r["stage"] or "(unknown stage)"].append(r)
    STAGE_ORDER = ["Design", "Fabrication", "Packaging", "Transit", "In-Field", "Disposal"]
    ordered = [s for s in STAGE_ORDER if s in by_stage] + [s for s in by_stage if s not in STAGE_ORDER]
    for stage in ordered:
        parts.append(f"<h2>{html.escape(stage)} ({len(by_stage[stage])})</h2>")
        for r in by_stage[stage]:
            doi = r["doi"]
            doi_link = f"https://doi.org/{doi}" if doi else ""
            parts.append('<div class="paper">')
            parts.append(f'<span class="tag">{html.escape(r["role"])}</span>')
            parts.append(f'<span class="tag">{html.escape(r["year"])}</span>')
            parts.append(f'<span class="tag">{html.escape(r["method"])}</span>')
            parts.append(f'<span class="tag">{html.escape(r["task"])}</span>')
            parts.append(f'<span class="title">{html.escape(r["title"])}</span>')
            parts.append(f'<span class="meta">{html.escape(r["author"])} · cites={html.escape(r["cites"])}</span><br>')
            if doi_link:
                parts.append(f'<a href="{html.escape(doi_link)}" target="_blank">{html.escape(doi)}</a>')
            else:
                parts.append('<span class="meta">(no DOI)</span>')
            key = (doi or "").lower()
            entry = abstracts.get(key)
            if entry and entry.get("abstract"):
                src = entry.get("source") or "?"
                parts.append(
                    f'<details><summary>Abstract <span class="src-tag">via {html.escape(src)}</span></summary>'
                    f'<div class="abstract">{html.escape(entry["abstract"])}</div></details>'
                )
            else:
                parts.append('<div class="abs-missing">(abstract unavailable from OpenAlex / Elsevier)</div>')
            parts.append("</div>")
    parts.append(HTML_FOOT)
    out_path.write_text("".join(parts), encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scopus_out10")
    md_path = outdir / "stage_shortlists.md"
    pdf_dir = outdir / "papers_oa"
    pdf_dir.mkdir(exist_ok=True)
    log_path = outdir / "papers_download_log.csv"
    html_path = outdir / "papers_manual.html"
    abs_cache_path = outdir / "abstracts_cache.json"

    # Load abstract cache (so repeated runs don't re-fetch)
    abs_cache = {}
    if abs_cache_path.exists():
        try:
            abs_cache = json.loads(abs_cache_path.read_text())
        except Exception:
            abs_cache = {}

    # Load Elsevier API key (fallback for abstracts)
    els_key = None
    try:
        if ELSEVIER_CONFIG.exists():
            els_key = json.loads(ELSEVIER_CONFIG.read_text()).get("apikey")
    except Exception:
        pass

    rows = extract_rows_from_md(md_path)
    print(f"Shortlist: {len(rows)} papers")

    downloaded = 0
    paywalled = []
    errored = 0
    no_doi = 0

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["stage", "role", "year", "author", "title", "doi",
                      "status", "oa_version", "oa_license", "filename", "notes"]
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for i, row in enumerate(rows, 1):
            out = dict(row, status="", oa_version="", oa_license="", filename="", notes="")
            if not row["doi"]:
                out["status"] = "no_doi"
                no_doi += 1
                print(f"  [{i:2d}/{len(rows)}] no DOI: {row['title'][:60]}")
                w.writerow(out); continue

            print(f"  [{i:2d}/{len(rows)}] {row['doi']}")
            info = unpaywall_lookup(row["doi"])
            time.sleep(DELAY)

            if "_error" in info:
                out["status"] = "unpaywall_err"; out["notes"] = info["_error"]
                errored += 1; paywalled.append(row); w.writerow(out); continue

            best = info.get("best_oa_location")
            if not best:
                out["status"] = "paywall"; out["notes"] = "no OA location"
                paywalled.append(row); w.writerow(out); continue

            pdf_url = best.get("url_for_pdf") or best.get("url")
            out["oa_version"] = best.get("version") or ""
            out["oa_license"] = best.get("license") or ""
            if not pdf_url:
                out["status"] = "no_pdf_url"
                paywalled.append(row); w.writerow(out); continue

            fname = (f"{row['stage']}_{row['year']}_"
                     f"{first_author_lastname(row['author'])}_"
                     f"{slugify(row['title'])}.pdf")
            dest = pdf_dir / fname
            ok, msg = download_pdf(pdf_url, dest)
            if ok:
                out["status"] = "downloaded"
                out["filename"] = fname
                out["notes"] = msg
                downloaded += 1
                print(f"       ✓ {fname} ({msg})")
            else:
                out["status"] = "download_failed"; out["notes"] = msg
                paywalled.append(row)
                print(f"       ✗ {msg}")
            w.writerow(out)

    # Fetch abstracts for every shortlist entry (OpenAlex → Elsevier fallback).
    # Uses a cache at abs_cache_path so repeated runs don't re-fetch.
    print("\nFetching abstracts…")
    abs_hits = 0
    abs_miss = 0
    for i, row in enumerate(rows, 1):
        if not row["doi"]:
            continue
        key = row["doi"].lower()
        if key in abs_cache and abs_cache[key].get("abstract"):
            abs_hits += 1
            continue
        abstract, src = fetch_abstract(row["doi"], abs_cache, els_key)
        if abstract:
            abs_hits += 1
            print(f"  [{i:2d}/{len(rows)}] {src}: {row['title'][:55]}")
        else:
            abs_miss += 1
            print(f"  [{i:2d}/{len(rows)}] no abstract: {row['title'][:55]}")
        time.sleep(DELAY)
    abs_cache_path.write_text(json.dumps(abs_cache, indent=1))

    summary = (f"Shortlist = {len(rows)}, downloaded = {downloaded}, "
               f"paywalled/manual = {len(paywalled)}, "
               f"errors = {errored}, no DOI = {no_doi}. "
               f"Abstracts available: {abs_hits}/{len(rows)}.")
    build_manual_html(paywalled, html_path, summary, abs_cache)

    print()
    print("=" * 60)
    print(summary)
    print(f"  PDFs:         {pdf_dir}/")
    print(f"  Manual HTML:  {html_path}")
    print(f"  Log:          {log_path}")
    print(f"  Abstracts:    {abs_cache_path}")


if __name__ == "__main__":
    main()
