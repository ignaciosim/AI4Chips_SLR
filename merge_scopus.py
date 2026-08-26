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

import re
import sys
import itertools
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

    # ── Extended-version collapse ───────────────────────────────────────
    # The dedup above keys on eid first, so a conference paper and its journal
    # extended version survive as two records (different eids, different DOIs,
    # identical title) and are counted twice. Collapse them to one study,
    # retaining the JOURNAL record as the version of record.
    def _norm_title(t):
        t = re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower())
        return " ".join(t.split())

    JOURNAL = "Journal"
    CONF = "Conference Proceeding"
    NEAR_JACCARD = 0.70

    def _surname(creator):
        c = (creator or "").strip()
        return re.sub(r"[^a-z]", "", c.split()[0].lower()) if c else ""

    def _fields(doc_id):
        e = seen[doc_id].get("entry", {}) or {}
        return (_norm_title(e.get("dc:title", "")),
                _surname(e.get("dc:creator", "")),
                e.get("prism:aggregationType", "") or "",
                (e.get("prism:coverDate", "") or "")[:4])

    dropped = set()
    collapsed = 0

    # (a) identical titles across source types
    by_title = {}
    for doc_id in seen:
        nt = _fields(doc_id)[0]
        if nt:
            by_title.setdefault(nt, []).append(doc_id)
    for ids in by_title.values():
        if len(ids) < 2:
            continue
        journals = [i for i in ids if _fields(i)[2] == JOURNAL]
        if not journals or len(journals) == len(ids):
            continue
        for i in ids:
            if i != journals[0]:
                dropped.add(i)
        collapsed += 1

    # (b) retitled journal extensions. Blocked on first-author surname to stay
    # tractable, and constrained to cross-type pairs where the journal version
    # is not older than the conference one, so unrelated same-author work on a
    # similar topic is not collapsed.
    blocks = {}
    for doc_id in seen:
        if doc_id in dropped:
            continue
        nt, sn, kind, yr = _fields(doc_id)
        if sn and nt:
            blocks.setdefault(sn, []).append(doc_id)
    for grp in blocks.values():
        for a, b in itertools.combinations(grp, 2):
            if a in dropped or b in dropped:
                continue
            ta, sa, ka, ya = _fields(a)
            tb, sb, kb, yb = _fields(b)
            if {ka, kb} != {JOURNAL, CONF}:
                continue
            wa, wb = set(ta.split()), set(tb.split())
            union = len(wa | wb)
            if not union:
                continue
            if len(wa & wb) / union < NEAR_JACCARD:
                continue
            conf, jour = (a, b) if ka == CONF else (b, a)
            ycf, yjr = _fields(conf)[3], _fields(jour)[3]
            if ycf and yjr and yjr >= ycf:
                dropped.add(conf)
                collapsed += 1

    if dropped:
        seen = {k: v for k, v in seen.items() if k not in dropped}
        rows = [r for r in rows if r["doc_id"] not in dropped]
        print(f"Extended-version pairs collapsed: {collapsed} "
              f"({len(dropped)} conference records dropped in favour of the "
              f"journal version)")

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
