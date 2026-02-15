#!/usr/bin/env python3
"""
merge_scopus.py — Merge and deduplicate raw_scopus_*.jsonl files.

Pure plumbing: no domain knowledge. Reads JSONL, deduplicates by EID/DOI/title,
writes merged JSONL + analysis-friendly CSV.

Usage:
    python merge_scopus.py <scopus_out_folder>

Example:
    python merge_scopus.py scopus_out
"""

import sys
import json
from pathlib import Path

import pandas as pd


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_scopus.py <scopus_out_folder>")
        sys.exit(1)

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Folder not found: {root}")

    jsonl_files = sorted(root.glob("raw_scopus_*.jsonl"))
    if not jsonl_files:
        raise SystemExit(f"No raw_scopus_*.jsonl files found in {root}")

    print("Merging from:")
    for p in jsonl_files:
        print(f"  - {p.name}")

    seen = {}
    rows = []

    for path in jsonl_files:
        print(f"Reading: {path.name}")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                rec = json.loads(line)
                entry = rec.get("entry", {}) or {}

                doc_id = (
                    entry.get("eid")
                    or entry.get("prism:doi")
                    or entry.get("dc:title")
                )
                if not doc_id or doc_id in seen:
                    continue

                seen[doc_id] = rec
                rows.append({
                    "doc_id": doc_id,
                    "stage": rec.get("stage"),
                    "year": rec.get("year"),
                    "title": entry.get("dc:title", "") or "",
                    "source": entry.get("prism:publicationName", "") or "",
                    "doi": entry.get("prism:doi", "") or "",
                    "coverDate": entry.get("prism:coverDate", "") or "",
                    "aggregationType": entry.get("prism:aggregationType", "") or "",
                    "subtype": entry.get("subtypeDescription", "") or "",
                })

    print(f"Unique papers: {len(seen)}")

    # Merged JSONL
    out_jsonl = root / "raw_scopus_all.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for rec in seen.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote: {out_jsonl}")

    # Merged CSV
    df = pd.DataFrame(rows).sort_values(["year", "source", "title"])
    out_csv = root / "raw_scopus_all.csv"
    df.to_csv(out_csv, index=False)
    print(f"Wrote: {out_csv}")

    # Venue stats
    venue_stats = (
        df.groupby("source").size()
        .reset_index(name="paper_count")
        .sort_values("paper_count", ascending=False)
    )
    venue_csv = root / "raw_scopus_venue_counts.csv"
    venue_stats.to_csv(venue_csv, index=False)
    print(f"Wrote: {venue_csv}")


if __name__ == "__main__":
    main()
