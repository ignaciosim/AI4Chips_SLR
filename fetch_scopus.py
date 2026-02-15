#!/usr/bin/env python3
"""
fetch_scopus.py — Fetch papers from Scopus Search API.

Queries per (lifecycle_phase, year) using vocabulary defined in slr_ontology.py.
No domain knowledge is hardcoded here — all query terms come from the ontology.

Outputs per phase:
    raw_scopus_<phase>.jsonl   (full entry JSON)
    raw_scopus_<phase>.csv     (flattened subset)
Plus:
    scopus_counts_by_stage_year.csv

Prereqs:
    pip install requests pandas

config.json:
    { "apikey": "YOUR_API_KEY" }
    Optional: { "apikey": "...", "insttoken": "YOUR_INSTTOKEN" }

Usage:
    python fetch_scopus.py --ai_focus --venues_file venues_eda.txt
    python fetch_scopus.py --start_year 2019 --end_year 2025 --ai_focus --max_pages 10
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import requests

from slr_ontology import PHASES, build_scopus_query


SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def last_full_year() -> int:
    return dt.datetime.now().year - 1


def load_cfg(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_venues(path: Path | None) -> List[str]:
    if path is None:
        return []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def scopus_search_page(
    cfg: dict, query: str, start: int, count: int,
) -> Tuple[int, List[dict], dict]:
    headers = {"X-ELS-APIKey": cfg["apikey"], "Accept": "application/json"}
    if cfg.get("insttoken"):
        headers["X-ELS-Insttoken"] = cfg["insttoken"]

    params = {"query": query, "start": str(start), "count": str(count)}
    r = requests.get(SCOPUS_SEARCH_URL, headers=headers, params=params, timeout=60)

    if not (200 <= r.status_code < 300):
        txt = (r.text or "")[:1200]
        raise RuntimeError(f"Scopus HTTP {r.status_code}. Body (trunc): {txt}")

    j = r.json()
    sr = j.get("search-results", {})
    total = int(sr.get("opensearch:totalResults", "0"))
    entries = sr.get("entry", []) or []
    return total, entries, j


def flatten_entry(e: dict) -> dict:
    return {
        "eid": e.get("eid", ""),
        "title": e.get("dc:title", ""),
        "creator": e.get("dc:creator", ""),
        "coverDate": e.get("prism:coverDate", ""),
        "publicationName": e.get("prism:publicationName", ""),
        "doi": e.get("prism:doi", ""),
        "citedby_count": e.get("citedby-count", ""),
        "subtype": e.get("subtypeDescription", ""),
        "aggregationType": e.get("prism:aggregationType", ""),
    }


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fetch Scopus papers per lifecycle phase.")
    ap.add_argument("--config", type=Path, default=Path("config.json"))
    ap.add_argument("--outdir", type=Path, default=Path("scopus_out"))
    ap.add_argument("--start_year", type=int, default=2016)
    ap.add_argument("--end_year", type=int, default=None,
                    help="Default: last full year")
    ap.add_argument("--ai_focus", action="store_true",
                    help="Add AI umbrella terms to narrow results")
    ap.add_argument("--venues_file", type=Path, default=None,
                    help="Optional allow-list of venues (one SRCTITLE per line)")
    ap.add_argument("--page_size", type=int, default=25)
    ap.add_argument("--max_pages", type=int, default=2,
                    help="Safety cap per query. Increase when stable.")
    ap.add_argument("--sleep_s", type=float, default=0.35)
    ap.add_argument("--print_queries", action="store_true")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    venues = load_venues(args.venues_file)

    end_year = args.end_year if args.end_year is not None else last_full_year()
    if end_year < args.start_year:
        raise ValueError("end_year < start_year")

    args.outdir.mkdir(parents=True, exist_ok=True)
    counts_rows: List[dict] = []
    failures: List[dict] = []

    # Smoke test
    smoke_q = build_scopus_query("design", end_year, ai_focus=args.ai_focus, venues=venues)
    total, entries, _ = scopus_search_page(cfg, smoke_q, start=0, count=1)
    print(f"SMOKE OK (design, {end_year}): total={total}")
    if entries:
        print(f"  First title: {entries[0].get('dc:title', '')}")

    for phase_key, phase in PHASES.items():
        jsonl_path = args.outdir / f"raw_scopus_{phase_key}.jsonl"
        csv_path = args.outdir / f"raw_scopus_{phase_key}.csv"

        base_fields = list(flatten_entry({}).keys())
        csv_fields = ["stage", "year", "query", "page_start", "page_index"] + base_fields

        with (
            open(jsonl_path, "w", encoding="utf-8") as jf,
            open(csv_path, "w", newline="", encoding="utf-8") as cf,
        ):
            writer = csv.DictWriter(cf, fieldnames=csv_fields)
            writer.writeheader()

            for year in range(args.start_year, end_year + 1):
                q = build_scopus_query(phase_key, year, ai_focus=args.ai_focus, venues=venues)
                if args.print_queries:
                    print(f"QUERY [{phase_key} {year}]: {q}")

                try:
                    total, _, _ = scopus_search_page(cfg, q, start=0, count=1)
                except Exception as ex:
                    failures.append({
                        "stage": phase_key, "year": year,
                        "query": q, "error": str(ex)[:400],
                    })
                    counts_rows.append({
                        "stage": phase_key, "year": year, "query": q,
                        "total": 0, "retrieved_rows": 0, "note": "request_failed",
                    })
                    print(f"[FAIL] {phase_key} {year}: {ex}")
                    time.sleep(args.sleep_s)
                    continue

                retrieved = 0
                pages_done = 0

                for page_idx in range(args.max_pages):
                    start = page_idx * args.page_size
                    if start >= total:
                        break

                    _, entries, _ = scopus_search_page(
                        cfg, q, start=start, count=args.page_size,
                    )
                    pages_done += 1

                    for e in entries:
                        rec = {
                            "stage": phase_key, "year": year,
                            "query": q, "page_start": start,
                            "page_index": page_idx, "entry": e,
                        }
                        jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        writer.writerow({
                            "stage": phase_key, "year": year,
                            "query": q, "page_start": start,
                            "page_index": page_idx,
                            **flatten_entry(e),
                        })
                        retrieved += 1

                    time.sleep(args.sleep_s)

                counts_rows.append({
                    "stage": phase_key, "year": year, "query": q,
                    "total": total, "retrieved_rows": retrieved,
                    "note": f"paged_{pages_done}_pages_capped",
                })
                print(f"[OK] {phase_key} {year}: total={total}, retrieved={retrieved}")
                time.sleep(args.sleep_s)

        print(f"Wrote {jsonl_path}")
        print(f"Wrote {csv_path}")

    # Counts summary
    counts_df = pd.DataFrame(counts_rows)
    if not counts_df.empty:
        year_tot = (
            counts_df.groupby("year")["total"]
            .sum().rename("year_total").reset_index()
        )
        counts_df = counts_df.merge(year_tot, on="year", how="left")
        counts_df["share_in_year"] = (
            counts_df["total"]
            / counts_df["year_total"].where(counts_df["year_total"] != 0, 1)
        )

    counts_csv = args.outdir / "scopus_counts_by_stage_year.csv"
    counts_df.to_csv(counts_csv, index=False)
    print(f"Wrote {counts_csv}")

    if failures:
        fail_csv = args.outdir / "scopus_failures.csv"
        pd.DataFrame(failures).to_csv(fail_csv, index=False)
        print(f"Wrote {fail_csv} (n={len(failures)})")


if __name__ == "__main__":
    main()
