#!/usr/bin/env python3
"""check_scopus_entitlement.py — Is this connection entitled to Scopus abstracts?

The Scopus API key alone is metadata-only: Abstract Retrieval returns coredata
without `dc:description`, and view=FULL / view=META_ABS return HTTP 401.
Elsevier grants the fuller entitlement either via an `insttoken` in
../config.json or by recognising the requesting IP as belonging to a
subscribing institution — so running this while on the university VPN (full
tunnel) can succeed where running it from a home connection does not.

Run it before and after connecting to the VPN and compare.

Usage:
    python3 analysis/check_scopus_entitlement.py
    python3 analysis/check_scopus_entitlement.py --config ../config.json
"""
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

# Probe record: taken from the corpus itself so it is guaranteed to exist in
# Scopus. Falls back to a fixed id if the corpus file is not present.
FALLBACK_SCOPUS_ID = "84922837643"


def probe_id(datadir="scopus_out12"):
    try:
        recs = json.loads(
            Path(datadir, "final_ai4chips_high_only.json").read_text())
        return recs[0]["doc_id"].replace("2-s2.0-", "")
    except Exception:
        return FALLBACK_SCOPUS_ID


def headers(cfg):
    h = {"X-ELS-APIKey": cfg["apikey"], "Accept": "application/json"}
    if cfg.get("insttoken"):
        h["X-ELS-Insttoken"] = cfg["insttoken"]
    return h


def probe(cfg, view=None):
    url = (f"https://api.elsevier.com/content/abstract/scopus_id/"
           f"{probe_id()}?httpAccept=application/json")
    if view:
        url += f"&view={view}"
    try:
        req = urllib.request.Request(url, headers=headers(cfg))
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.load(r)
        core = (d.get("abstracts-retrieval-response", {})
                 .get("coredata", {}) or {})
        abstract = core.get("dc:description") or ""
        return ("OK", len(abstract))
    except urllib.error.HTTPError as e:
        return (f"HTTP {e.code}", 0)
    except Exception as e:
        return (type(e).__name__, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="../config.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())

    print(f"insttoken present in config: {bool(cfg.get('insttoken'))}\n")
    print(f"{'view':12}{'result':>12}{'abstract chars':>17}")
    print("-" * 41)
    entitled = False
    for view in (None, "META_ABS", "FULL"):
        status, n = probe(cfg, view)
        if status == "OK" and n > 0:
            entitled = True
        print(f"{view or 'default':12}{status:>12}{n:>17}")

    print()
    if entitled:
        print("ENTITLED — Scopus abstracts are available on this connection.")
        print("Re-run the retrieval so abstracts land in the JSONL, e.g.:")
        print("  make all DATADIR=scopus_out13")
        print("or classify with abstracts:")
        print("  python3 classify_scopus.py scopus_out13/ --from_jsonl")
    else:
        print("NOT ENTITLED on this connection (metadata only).")
        print("Options: connect via the university VPN with FULL tunnelling,")
        print("or ask the library for an Elsevier insttoken and add it to")
        print("config.json as {\"apikey\": \"...\", \"insttoken\": \"...\"}.")
        print("Fallback already in place: analysis/fetch_abstracts.py "
              "(OpenAlex).")


if __name__ == "__main__":
    main()
