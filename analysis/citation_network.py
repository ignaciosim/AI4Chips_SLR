#!/usr/bin/env python3
"""
Citation-network analysis via OpenAlex.

Fetches full author lists and reference lists for every paper in the corpus,
builds an intra-corpus citation graph, and reports:
  - intra-corpus citation density
  - author self-citations (paper cites another paper sharing ≥1 author)
  - circular citation pairs  (A cites B  AND  B cites A)
  - longer citation cycles    (A→B→C→…→A)
  - most-cited papers within the corpus

Works on both the ai4chips-only set and the full corpus.

Usage:
    python3 analysis/citation_network.py                  # ai4chips (221 papers)
    python3 analysis/citation_network.py --full-corpus    # all 4 982 papers
    python3 analysis/citation_network.py --cache-only     # skip fetch, reuse cache
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DATA = BASE / os.environ.get("SLR_DATADIR", "scopus_out7")
CACHE_DIR = DATA / "openalex_cache"

AI4CHIPS_JSON = DATA / "final_ai4chips_high_only.json"
FULL_JSONL = DATA / "raw_scopus_all.jsonl"

MAILTO = "slr-pipeline@example.com"  # polite-pool identifier
BATCH = 50  # OpenAlex max per_page
DELAY = 0.12  # ~8 req/s  (polite pool allows 10)


# ── data loading ─────────────────────────────────────────────────────────
def load_ai4chips_dois() -> dict[str, dict]:
    """Return {doi_lower: {title, year, creator, doc_id}} for ai4chips papers."""
    with open(AI4CHIPS_JSON) as f:
        data = json.load(f)
    out = {}
    for r in data:
        doi = r.get("doi", "").strip().lower()
        if doi:
            out[doi] = dict(
                title=r.get("title", ""),
                year=r.get("year"),
                creator=r.get("creator", ""),
                doc_id=r.get("doc_id", ""),
            )
    return out


def load_full_corpus_dois() -> dict[str, dict]:
    """Return {doi_lower: {title, year, creator, doc_id}} for full corpus."""
    out = {}
    with open(FULL_JSONL) as f:
        for line in f:
            d = json.loads(line)
            entry = d["entry"]
            doi = (entry.get("prism:doi") or "").strip().lower()
            if doi:
                out[doi] = dict(
                    title=entry.get("dc:title", ""),
                    year=d.get("year"),
                    creator=entry.get("dc:creator", ""),
                    doc_id=entry.get("eid", ""),
                )
    return out


# ── OpenAlex fetching ────────────────────────────────────────────────────
def _openalex_batch(dois: list[str]) -> list[dict]:
    """Fetch a batch of works by DOI.  Returns raw result dicts."""
    doi_filter = "|".join(f"https://doi.org/{d}" for d in dois)
    params = urllib.parse.urlencode(
        {
            "filter": f"doi:{doi_filter}",
            "per_page": BATCH,
            "mailto": MAILTO,
            "select": "id,doi,title,authorships,referenced_works,cited_by_count",
        }
    )
    url = f"https://api.openalex.org/works?{params}"
    req = urllib.request.Request(url)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data.get("results", [])
        except Exception as exc:
            if attempt == 3:
                print(f"  WARN: batch failed after 4 attempts: {exc}", file=sys.stderr)
                return []
            wait = 2 ** attempt
            print(f"  retry in {wait}s ({exc})", file=sys.stderr)
            time.sleep(wait)
    return []


def fetch_openalex(dois: list[str], cache_file: Path) -> dict[str, dict]:
    """
    Fetch OpenAlex data for all DOIs.  Caches results to JSON.

    Returns {doi_lower: {openalex_id, author_ids: set[str],
                          referenced_oa_ids: list[str]}}.
    """
    if cache_file.exists():
        print(f"  Loading cache: {cache_file}")
        with open(cache_file) as f:
            raw = json.load(f)
        # convert author_ids back to sets
        return {
            k: {**v, "author_ids": set(v["author_ids"]),
                 "author_names": v.get("author_names", {})}
            for k, v in raw.items()
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    batches = [dois[i : i + BATCH] for i in range(0, len(dois), BATCH)]
    print(f"  Fetching {len(dois)} papers in {len(batches)} batches …")

    for bi, batch in enumerate(batches):
        recs = _openalex_batch(batch)
        for r in recs:
            doi = (r.get("doi") or "").replace("https://doi.org/", "").lower()
            oa_id = r.get("id", "")
            author_ids = set()
            author_names: dict[str, str] = {}  # id → display_name
            for a in r.get("authorships", []):
                author = a.get("author") or {}
                aid = author.get("id")
                if aid:
                    author_ids.add(aid)
                    author_names[aid] = author.get("display_name", "")
            refs = r.get("referenced_works", [])
            results[doi] = dict(
                openalex_id=oa_id,
                author_ids=author_ids,
                author_names=author_names,
                referenced_oa_ids=refs,
                cited_by_count=r.get("cited_by_count", 0),
            )
        if (bi + 1) % 10 == 0 or bi == len(batches) - 1:
            print(f"    {bi+1}/{len(batches)} batches  ({len(results)} resolved)")
        time.sleep(DELAY)

    # save cache  (sets → lists for JSON)
    serial = {k: {**v, "author_ids": list(v["author_ids"])} for k, v in results.items()}
    with open(cache_file, "w") as f:
        json.dump(serial, f)
    print(f"  Cached to {cache_file}")
    return results


# ── graph analysis ───────────────────────────────────────────────────────
def build_graph(
    corpus_dois: dict[str, dict], oa_data: dict[str, dict]
) -> tuple[
    dict[str, list[str]],  # adjacency: doi → [cited dois in corpus]
    dict[str, set[str]],   # author map: doi → author OA ids
    dict[str, str],        # oa_id → doi  reverse map
]:
    """Build intra-corpus citation adjacency list."""
    # map OpenAlex IDs back to corpus DOIs
    oaid_to_doi: dict[str, str] = {}
    for doi, info in oa_data.items():
        if doi in corpus_dois:
            oaid_to_doi[info["openalex_id"]] = doi

    adj: dict[str, list[str]] = defaultdict(list)
    author_map: dict[str, set[str]] = {}

    for doi in corpus_dois:
        info = oa_data.get(doi)
        if not info:
            continue
        author_map[doi] = info["author_ids"]
        for ref_id in info["referenced_oa_ids"]:
            cited_doi = oaid_to_doi.get(ref_id)
            if cited_doi and cited_doi != doi:  # skip literal self-ref
                adj[doi].append(cited_doi)

    return dict(adj), author_map, oaid_to_doi


def find_self_citations(
    adj: dict[str, list[str]], author_map: dict[str, set[str]]
) -> list[tuple[str, str, set[str]]]:
    """Return (citing_doi, cited_doi, shared_author_ids) for author self-cites."""
    hits = []
    for src, targets in adj.items():
        src_authors = author_map.get(src, set())
        if not src_authors:
            continue
        for tgt in targets:
            tgt_authors = author_map.get(tgt, set())
            shared = src_authors & tgt_authors
            if shared:
                hits.append((src, tgt, shared))
    return hits


def find_circular_pairs(adj: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Return sorted list of (doi_a, doi_b) where A cites B AND B cites A."""
    edges = set()
    for src, targets in adj.items():
        for tgt in targets:
            edges.add((src, tgt))
    pairs = set()
    for a, b in edges:
        if (b, a) in edges:
            pair = tuple(sorted([a, b]))
            pairs.add(pair)
    return sorted(pairs)


def find_cycles(adj: dict[str, list[str]], max_length: int = 5) -> list[list[str]]:
    """Find all cycles up to max_length using DFS. Returns unique cycles."""
    all_nodes = set(adj.keys())
    for targets in adj.values():
        all_nodes.update(targets)

    cycles: list[tuple[str, ...]] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def dfs(start: str, path: list[str], visited: set[str]):
        if len(path) > max_length:
            return
        current = path[-1]
        for nxt in adj.get(current, []):
            if nxt == start and len(path) >= 2:
                # normalize: rotate so smallest DOI is first
                c = tuple(path)
                mn = min(c)
                idx = c.index(mn)
                canon = c[idx:] + c[:idx]
                if canon not in seen_cycles:
                    seen_cycles.add(canon)
                    cycles.append(list(canon))
            elif nxt not in visited and len(path) < max_length:
                visited.add(nxt)
                path.append(nxt)
                dfs(start, path, visited)
                path.pop()
                visited.discard(nxt)

    for node in sorted(all_nodes):
        dfs(node, [node], {node})

    return sorted(cycles, key=lambda c: (len(c), c))


def in_degree(adj: dict[str, list[str]]) -> dict[str, int]:
    """Count how many corpus papers cite each paper."""
    counts: dict[str, int] = defaultdict(int)
    for targets in adj.values():
        for t in targets:
            counts[t] += 1
    return dict(counts)


# ── reporting ────────────────────────────────────────────────────────────
def report(
    corpus_dois: dict[str, dict],
    oa_data: dict[str, dict],
    adj: dict[str, list[str]],
    author_map: dict[str, set[str]],
    label: str,
):
    n_corpus = len(corpus_dois)
    n_resolved = sum(1 for d in corpus_dois if d in oa_data)
    n_edges = sum(len(v) for v in adj.values())
    n_with_intra = sum(1 for v in adj.values() if v)

    print(f"\n{'='*65}")
    print(f"  Citation Network Analysis — {label}")
    print(f"{'='*65}")
    print(f"  Corpus size          : {n_corpus:,}")
    print(f"  Resolved in OpenAlex : {n_resolved:,}  ({100*n_resolved/n_corpus:.1f}%)")
    print(f"  Intra-corpus edges   : {n_edges:,}")
    print(f"  Papers citing corpus : {n_with_intra:,}  ({100*n_with_intra/n_resolved:.1f}% of resolved)")
    if n_resolved:
        print(f"  Mean intra-refs/paper: {n_edges/n_resolved:.2f}")

    # ── top cited within corpus ──
    indeg = in_degree(adj)
    if indeg:
        print(f"\n  Top 15 most-cited within corpus:")
        for doi, cnt in sorted(indeg.items(), key=lambda x: -x[1])[:15]:
            meta = corpus_dois.get(doi, {})
            title = (meta.get("title") or "")[:55]
            year = meta.get("year", "?")
            print(f"    {cnt:3d} cites ← {year} | {title}")

    # ── self-citations ──
    self_cites = find_self_citations(adj, author_map)
    print(f"\n  Author self-citations : {len(self_cites):,}")
    if self_cites:
        pct = 100 * len(self_cites) / n_edges if n_edges else 0
        print(f"    ({pct:.1f}% of intra-corpus edges)")
        # top self-citing authors
        author_self: dict[str, int] = defaultdict(int)
        for _, _, shared in self_cites:
            for a in shared:
                author_self[a] += 1
        # resolve author names from oa_data
        aid_to_name: dict[str, str] = {}
        for doi, info in oa_data.items():
            for aid, name in info.get("author_names", {}).items():
                if name:
                    aid_to_name[aid] = name
        print(f"  Distinct self-citing author IDs: {len(author_self)}")
        print(f"  Top self-citing authors (by # self-cite edges):")
        for aid, cnt in sorted(author_self.items(), key=lambda x: -x[1])[:10]:
            name = aid_to_name.get(aid, aid)
            print(f"    {cnt:3d} edges — {name}")

    # ── circular pairs ──
    circ = find_circular_pairs(adj)
    print(f"\n  Circular citation pairs (A↔B): {len(circ)}")
    for i, (a, b) in enumerate(circ):
        ma, mb = corpus_dois.get(a, {}), corpus_dois.get(b, {})
        ya, yb = ma.get("year", "?"), mb.get("year", "?")
        print(f"\n    Pair {i+1}:")
        print(f"      A: ({ya}) {ma.get('title','?')}")
        print(f"         doi: {a}")
        print(f"      B: ({yb}) {mb.get('title','?')}")
        print(f"         doi: {b}")
        # check if also a self-citation
        shared = (author_map.get(a, set()) & author_map.get(b, set()))
        if shared:
            names = [aid_to_name.get(aid, aid) for aid in shared]
            print(f"      Shared authors: {', '.join(names)}")

    # ── longer cycles ──
    print(f"\n  Searching for cycles (length 3-5) …")
    cycles = find_cycles(adj, max_length=5)
    # exclude length-2 (already reported as circular pairs)
    longer = [c for c in cycles if len(c) > 2]
    print(f"  Cycles found (length 3-5): {len(longer)}")
    for ci, c in enumerate(longer[:15]):
        print(f"\n    Cycle {ci+1} (length {len(c)}):")
        for j, doi in enumerate(c):
            m = corpus_dois.get(doi, {})
            yr = m.get("year", "?")
            title = (m.get("title") or "?")[:65]
            arrow = "→" if j < len(c) - 1 else "→ (back to 1)"
            print(f"      {j+1}. ({yr}) {title}  {arrow}")
    if len(longer) > 15:
        print(f"    … and {len(longer)-15} more")

    # ── summary stats ──
    self_cite_dois = set()
    for s, t, _ in self_cites:
        self_cite_dois.add(s)
    circ_dois = set()
    for a, b in circ:
        circ_dois.add(a)
        circ_dois.add(b)

    print(f"\n  Summary:")
    print(f"    Papers involved in self-citation  : {len(self_cite_dois):,}")
    print(f"    Papers involved in circular pairs  : {len(circ_dois):,}")
    print(f"    Papers involved in longer cycles   : {len(set(d for c in longer for d in c)):,}")
    print()


# ── main ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Citation network via OpenAlex")
    parser.add_argument("--full-corpus", action="store_true",
                        help="Analyse full corpus (N≈5 000) instead of ai4chips only")
    parser.add_argument("--cache-only", action="store_true",
                        help="Skip fetching, use existing cache")
    args = parser.parse_args()

    if args.full_corpus:
        label = "Full corpus"
        corpus_dois = load_full_corpus_dois()
        cache_file = CACHE_DIR / "openalex_full.json"
    else:
        label = "AI-for-chips high-confidence"
        corpus_dois = load_ai4chips_dois()
        cache_file = CACHE_DIR / "openalex_ai4chips.json"

    print(f"\n  {label}: {len(corpus_dois):,} papers with DOIs")

    if args.cache_only and not cache_file.exists():
        print(f"  ERROR: cache not found at {cache_file}", file=sys.stderr)
        sys.exit(1)

    if args.cache_only:
        oa_data = fetch_openalex([], cache_file)  # will just load cache
    else:
        oa_data = fetch_openalex(list(corpus_dois.keys()), cache_file)

    adj, author_map, _ = build_graph(corpus_dois, oa_data)
    report(corpus_dois, oa_data, adj, author_map, label)


if __name__ == "__main__":
    main()
