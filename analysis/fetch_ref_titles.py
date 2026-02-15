#!/usr/bin/env python3
"""
Fetch titles and years for all external references cited by the corpus.

Produces:
  - openalex_cache/ref_metadata_full.json  (id → {title, year, doi})
  - scopus_out7/external_references.csv    (readable table)

Usage:
    python3 analysis/fetch_ref_titles.py
    python3 analysis/fetch_ref_titles.py --cache-only   # skip fetch, just export CSV
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "scopus_out7"
CACHE_DIR = DATA / "openalex_cache"
OA_FULL = CACHE_DIR / "openalex_full.json"
REF_META_CACHE = CACHE_DIR / "ref_metadata_full.json"
CSV_OUT = DATA / "external_references.csv"

MAILTO = "slr-pipeline@example.com"
BATCH = 50
DELAY = 0.12


def collect_ref_ids() -> tuple[set[str], dict[str, int]]:
    """Return (all external ref IDs, {ref_id: cite_count})."""
    with open(OA_FULL) as f:
        oa = json.load(f)
    corpus_ids = set(info["openalex_id"] for info in oa.values())
    ref_counts: dict[str, int] = Counter()
    for info in oa.values():
        for ref_id in info.get("referenced_oa_ids", []):
            ref_counts[ref_id] += 1
    external = {rid for rid in ref_counts if rid not in corpus_ids}
    return external, ref_counts


def fetch_batch(oa_ids: list[str]) -> list[dict]:
    id_filter = "|".join(oa_ids)
    params = urllib.parse.urlencode({
        "filter": f"openalex_id:{id_filter}",
        "per_page": BATCH,
        "mailto": MAILTO,
        "select": "id,title,publication_year,doi",
    })
    url = f"https://api.openalex.org/works?{params}"
    req = urllib.request.Request(url)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data.get("results", [])
        except Exception as exc:
            if attempt == 3:
                print(f"  WARN: batch failed: {exc}", file=sys.stderr)
                return []
            time.sleep(2 ** attempt)
    return []


def fetch_all(ref_ids: set[str]) -> dict[str, dict]:
    """Fetch {oa_id: {title, year, doi}} for all ref IDs. Caches."""
    if REF_META_CACHE.exists():
        print(f"  Loading cache: {REF_META_CACHE}")
        with open(REF_META_CACHE) as f:
            return json.load(f)

    ids = sorted(ref_ids)
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]
    print(f"  Fetching metadata for {len(ids):,} refs ({len(batches):,} batches) …")

    result: dict[str, dict] = {}
    for bi, batch in enumerate(batches):
        recs = fetch_batch(batch)
        for r in recs:
            oa_id = r.get("id", "")
            result[oa_id] = dict(
                title=r.get("title", ""),
                year=r.get("publication_year"),
                doi=(r.get("doi") or "").replace("https://doi.org/", ""),
            )
        if (bi + 1) % 100 == 0 or bi == len(batches) - 1:
            print(f"    {bi+1:,}/{len(batches):,}  ({len(result):,} resolved)")
        time.sleep(DELAY)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(REF_META_CACHE, "w") as f:
        json.dump(result, f)
    print(f"  Cached to {REF_META_CACHE}")
    return result


def export_csv(ref_meta: dict[str, dict], ref_counts: dict[str, int]):
    """Write a CSV of all external references sorted by citation count."""
    rows = []
    for oa_id, meta in ref_meta.items():
        rows.append(dict(
            openalex_id=oa_id,
            title=meta.get("title", ""),
            year=meta.get("year", ""),
            doi=meta.get("doi", ""),
            cited_by_n_corpus_papers=ref_counts.get(oa_id, 0),
        ))
    rows.sort(key=lambda r: -r["cited_by_n_corpus_papers"])

    with open(CSV_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "cited_by_n_corpus_papers", "year", "title", "doi", "openalex_id"])
        w.writeheader()
        w.writerows(rows)
    print(f"  Wrote {len(rows):,} rows to {CSV_OUT}")

    # summary
    print(f"\n  Top 30 most-cited external references:")
    print(f"  {'N':>4s}  {'Year':>4s}  Title")
    for r in rows[:30]:
        title = (r["title"] or "")[:75]
        print(f"  {r['cited_by_n_corpus_papers']:4d}  {r['year'] or '?':>4}  {title}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()

    if not OA_FULL.exists():
        print(f"  ERROR: run citation_network.py --full-corpus first", file=sys.stderr)
        sys.exit(1)

    external_ids, ref_counts = collect_ref_ids()
    print(f"  External references: {len(external_ids):,}")

    if args.cache_only and not REF_META_CACHE.exists():
        print(f"  ERROR: no cache at {REF_META_CACHE}", file=sys.stderr)
        sys.exit(1)

    ref_meta = fetch_all(external_ids)
    export_csv(ref_meta, ref_counts)


if __name__ == "__main__":
    main()
