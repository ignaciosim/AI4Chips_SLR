#!/usr/bin/env python3
"""fetch_abstracts.py — Retrieve abstracts for a corpus via OpenAlex.

The Scopus API key used by `fetch_scopus.py` is entitled for metadata only:
the Abstract Retrieval API returns `coredata` without `dc:description`, and
`view=FULL` / `view=META_ABS` return HTTP 401. Abstracts therefore come from
OpenAlex, which is open, needs no key, and stores abstracts as an inverted
index that this script reconstructs into plain text.

Lookup order per paper: DOI, then exact-ish title search. Results are cached
so re-runs are cheap and resumable; interrupting and restarting is safe.

Usage:
    python3 analysis/fetch_abstracts.py --datadir scopus_out12
    python3 analysis/fetch_abstracts.py --datadir scopus_out12 --limit 50

Output:
    <datadir>/abstracts_openalex.json
        {doc_id: {"abstract": str, "source": "doi"|"title", "openalex_id": str,
                  "n_chars": int}}
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OPENALEX = "https://api.openalex.org/works"
# OpenAlex asks for a contact address in the polite pool; it buys higher
# rate limits and lets them reach us if a script misbehaves.
MAILTO = "ignacio.chechile@gmail.com"
UA = f"slr-ai4chips-pipeline/1.0 (mailto:{MAILTO})"

RETRY_ATTEMPTS = 4
RETRY_BACKOFF_S = 2
SLEEP_S = 0.12
SS_SLEEP_S = 1.1          # Semantic Scholar unauthenticated rate limit
MIN_USABLE_CHARS = 200


def _get(url):
    """GET with retry on transient failures. Returns parsed JSON or None."""
    last = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None            # genuinely absent, not an error
            if e.code in (429, 500, 502, 503, 504):
                last = e
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
                continue
            return None
        except Exception as e:         # network drop, timeout, bad JSON
            last = e
            time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
    if last:
        print(f"    [give up] {type(last).__name__}")
    return None


def inverted_to_text(inv):
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def by_doi(doi):
    url = f"{OPENALEX}/doi:{urllib.parse.quote(doi.lower())}?mailto={MAILTO}"
    return _get(url)


def by_semantic_scholar(doi):
    """Second source. OpenAlex lags on very recent journal articles and on
    some IEEE/Elsevier records; Semantic Scholar often has those. Crossref
    was tested and returns nothing useful here (these publishers do not
    deposit abstracts), so it is not used."""
    url = ("https://api.semanticscholar.org/graph/v1/paper/DOI:"
           f"{urllib.parse.quote(doi.lower())}?fields=abstract,externalIds")
    d = _get(url)
    return (d or {}).get("abstract") or ""


def by_title(title):
    q = urllib.parse.quote(title[:250])
    url = (f"{OPENALEX}?filter=title.search:{q}"
           f"&per-page=1&mailto={MAILTO}")
    d = _get(url)
    results = (d or {}).get("results") or []
    return results[0] if results else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out12")
    ap.add_argument("--corpus", default="final_ai4chips_high_only.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    d = Path(args.datadir)
    papers = json.loads((d / args.corpus).read_text())
    out_path = Path(args.out) if args.out else d / "abstracts_openalex.json"

    cache = {}
    if out_path.exists():
        cache = json.loads(out_path.read_text())
        print(f"resuming from cache: {len(cache)} entries")

    todo = [p for p in papers if p["doc_id"] not in cache]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(papers)} papers, {len(todo)} to fetch")

    for i, p in enumerate(todo, 1):
        doc_id, doi = p["doc_id"], (p.get("doi") or "").strip()
        rec, source = None, None
        if doi:
            rec, source = by_doi(doi), "doi"
        if rec is None:
            rec, source = by_title(p.get("title", "")), "title"

        abstract = inverted_to_text((rec or {}).get("abstract_inverted_index"))

        # Fall back to Semantic Scholar when OpenAlex has the record but no
        # abstract text (common for 2025-2026 journal articles).
        if len(abstract) < MIN_USABLE_CHARS and doi:
            s2 = by_semantic_scholar(doi)
            if len(s2) > len(abstract):
                abstract, source = s2, "semanticscholar"
            time.sleep(SS_SLEEP_S)

        cache[doc_id] = {
            "abstract": abstract,
            "source": source if (rec or abstract) else None,
            "openalex_id": (rec or {}).get("id"),
            "n_chars": len(abstract),
        }
        if i % 50 == 0 or i == len(todo):
            out_path.write_text(json.dumps(cache, indent=1))
            got = sum(1 for v in cache.values()
                      if v["n_chars"] >= MIN_USABLE_CHARS)
            print(f"  [{i}/{len(todo)}] cached={len(cache)} usable={got}",
                  flush=True)
        time.sleep(SLEEP_S)

    out_path.write_text(json.dumps(cache, indent=1))
    usable = sum(1 for v in cache.values() if v["n_chars"] >= MIN_USABLE_CHARS)
    empty = sum(1 for v in cache.values() if v["n_chars"] == 0)
    print(f"\nwrote {out_path}")
    print(f"  total cached : {len(cache)}")
    print(f"  usable (>={MIN_USABLE_CHARS} chars): {usable} "
          f"({100*usable/max(len(cache),1):.1f}%)")
    print(f"  empty        : {empty}")


if __name__ == "__main__":
    main()
