#!/usr/bin/env python3
"""conference_sensitivity.py — Reviewer 1 comment 1 sensitivity analysis.

Runs the ontology classifier over a conference corpus retrieved with
`fetch_scopus.py --conferences` and compares the resulting AI-method mix
against the journal corpus that forms the review's headline dataset.

It answers three questions the reviewer raised:

  1. Does the relative prevalence of AI methods (LLM, RL, GNN, ...) differ
     between journal and conference literature?
  2. How much of the conference literature is duplicated by journal
     extended versions already in the corpus (the double-counting confound
     that motivates a journal-only headline dataset)?
  3. Do EDA conferences (DAC/ICCAD/DATE) and general ML conferences
     (NeurIPS/ICML/AAAI/ICLR) behave differently?

Usage:
    python3 analysis/conference_sensitivity.py \\
        --confdir scopus_conf --journaldir scopus_out11
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import slr_ontology as onto  # noqa: E402

# Scopus records these events under several source-title variants (hyphen /
# comma / year-prefixed proceedings names), so match on normalised substrings.
EDA_VENUES = ("design automation conference", "computer-aided design",
              "computer aided design", "design, automation and test",
              "design automation and test")
# ...but "computer aided design" also matches unrelated CAD events, so these
# are excluded explicitly.
EDA_EXCLUDE = ("thin film transistor", "computer graphics")
ML_VENUES = ("neural information processing", "machine learning",
             "artificial intelligence", "learning representations")
# Non-design conference venues (fabrication / packaging / test / reliability),
# retrieved to balance the design-automation venues above.
ND_VENUES = ("advanced semiconductor manufacturing",
             "symposium on semiconductor manufacturing",
             "electron devices meeting",
             "simulation of semiconductor processes",
             "symposium on vlsi technology",
             "electronic components and technology",
             "thermal and thermomechanical",
             "international test conference",
             "vlsi test symposium",
             "asian test symposium",
             "reliability physics symposium",
             "physical and failure analysis")


def venue_group(name):
    n = (name or "").lower()
    if any(v in n for v in ND_VENUES):
        return "NONDESIGN"
    if any(v in n for v in EDA_EXCLUDE):
        return "other"
    if any(v in n for v in EDA_VENUES):
        return "EDA"
    if any(v in n for v in ML_VENUES):
        return "ML"
    return "other"


def norm_title(t):
    """Normalise a title for duplicate detection across venue types."""
    t = (t or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())


def load_conf(confdir):
    """Read every raw_scopus_*.jsonl in the conference directory."""
    seen, rows = set(), []
    for path in sorted(Path(confdir).glob("raw_scopus_*.jsonl")):
        stage = path.stem.replace("raw_scopus_", "")
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                e = rec.get("entry", rec)
                eid = e.get("eid") or e.get("dc:identifier", "")
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                rows.append({
                    "eid": eid,
                    "stage": rec.get("stage", stage),
                    "title": e.get("dc:title", ""),
                    "venue": e.get("prism:publicationName", ""),
                    "year": (e.get("prism:coverDate", "") or "")[:4],
                })
    return rows


def classify(rows):
    """Apply the ontology directionality rule; keep high-confidence ai4chips."""
    kept = []
    for r in rows:
        title = r["title"]
        m = onto.match_ontology_classes(title, onto.AI_METHODS)
        t = onto.match_ontology_classes(title, onto.CHIP_DESIGN_TASKS)
        a = onto.match_ontology_classes(title, onto.HW_ARTIFACTS)
        w = onto.match_ontology_classes(title, onto.AI_WORKLOADS)
        if m and t and not a and not w:
            r = dict(r)
            r["methods"] = sorted(onto.detect_ai_methods(title))
            kept.append(r)
    return kept


def pct_table(counter, total):
    return {k: (v, 100.0 * v / total if total else 0.0)
            for k, v in counter.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confdir", action="append", default=None,
                    help="Conference data directory; repeat for several.")
    ap.add_argument("--journaldir", default="scopus_out11")
    args = ap.parse_args()

    confdirs = args.confdir or ["scopus_conf"]
    raw, seen = [], set()
    for d in confdirs:
        for r in load_conf(d):
            if r["eid"] in seen:
                continue
            seen.add(r["eid"])
            raw.append(r)
    print(f"conference records retrieved (deduplicated): {len(raw)}")
    grp = Counter(venue_group(r["venue"]) for r in raw)
    print(f"  by venue group: {dict(grp)}\n")

    kept = classify(raw)
    print(f"pass ontology high-confidence ai4chips rule: {len(kept)} "
          f"({100.0*len(kept)/len(raw):.1f}% of retrieved)")
    kgrp = Counter(venue_group(r["venue"]) for r in kept)
    print(f"  by venue group: {dict(kgrp)}\n")

    # ── journal corpus for comparison ───────────────────────────────────
    jrows = list(csv.DictReader(
        open(Path(args.journaldir) / "final_ai4chips_high_only.csv")))
    jm = Counter()
    for r in jrows:
        for t in r["method_tags"].split(";"):
            t = t.strip()
            if t:
                jm[t] += 1

    print("=" * 72)
    print("AI METHOD MIX — journal corpus vs conference corpus (% of corpus)")
    print("=" * 72)
    groups = {g: [r for r in kept if venue_group(r["venue"]) == g]
              for g in ("EDA", "NONDESIGN", "ML")}
    cm = {g: Counter(m for r in rs for m in r["methods"])
          for g, rs in groups.items()}

    keys = sorted(set(jm) | {k for c in cm.values() for k in c},
                  key=lambda k: -jm.get(k, 0))
    hdr = (f"{'method':26}{'journal':>10}{'design cf':>11}{'non-des cf':>12}"
           f"{'ML cf':>8}{'COMBINED':>11}{'shift':>8}")
    print(hdr)
    print("-" * len(hdr))
    allc = Counter(m for rs in groups.values() for r in rs for m in r["methods"])
    comb_n = len(jrows) + sum(len(v) for v in groups.values())
    for k in keys:
        jp = 100.0 * jm.get(k, 0) / len(jrows)
        ep = 100.0 * cm["EDA"].get(k, 0) / max(len(groups["EDA"]), 1)
        np_ = 100.0 * cm["NONDESIGN"].get(k, 0) / max(len(groups["NONDESIGN"]), 1)
        mp = 100.0 * cm["ML"].get(k, 0) / max(len(groups["ML"]), 1)
        cp = 100.0 * (jm.get(k, 0) + allc.get(k, 0)) / max(comb_n, 1)
        flag = " <<<" if abs(cp - jp) >= 4 else ""
        print(f"{k:26}{jp:>9.1f}%{ep:>10.1f}%{np_:>11.1f}%{mp:>7.1f}%"
              f"{cp:>10.1f}%{cp-jp:>+7.1f}{flag}")
    print(f"\n  N: journal={len(jrows)}  design conf={len(groups['EDA'])}  "
          f"non-design conf={len(groups['NONDESIGN'])}  ML conf={len(groups['ML'])}"
          f"  COMBINED={comb_n}")

    # ── lifecycle stage balance ─────────────────────────────────────────
    STAGES = ["design", "fabrication", "packaging", "transit", "in_field",
              "disposal"]
    js = Counter(r["stage"] for r in jrows)
    ds = Counter(r["stage"] for r in groups["EDA"])
    ns = Counter(r["stage"] for r in groups.get("NONDESIGN", []))
    tot_c = len(groups["EDA"]) + len(groups.get("NONDESIGN", []))
    comb = len(jrows) + tot_c
    print("\n" + "=" * 78)
    print("LIFECYCLE STAGE BALANCE")
    print("=" * 78)
    print(f"  {'stage':13}{'journal':>14}{'design conf':>15}"
          f"{'non-design conf':>18}{'COMBINED':>15}")
    print("  " + "-" * 74)
    for st in STAGES:
        c = js[st] + ds[st] + ns[st]
        print(f"  {st:13}{js[st]:>6} {100*js[st]/max(len(jrows),1):>5.1f}%"
              f"{ds[st]:>7} {100*ds[st]/max(len(groups['EDA']),1):>5.1f}%"
              f"{ns[st]:>10} {100*ns[st]/max(len(groups.get('NONDESIGN',[])),1):>5.1f}%"
              f"{c:>7} {100*c/max(comb,1):>5.1f}%")
    print("  " + "-" * 74)
    print(f"  {'TOTAL':13}{len(jrows):>6} {100.0:>5.1f}%"
          f"{len(groups['EDA']):>7} {100.0:>5.1f}%"
          f"{len(groups.get('NONDESIGN',[])):>10} {100.0:>5.1f}%"
          f"{comb:>7} {100.0:>5.1f}%")
    dj = 100*js['design']/max(len(jrows),1)
    dc = 100*(js['design']+ds['design']+ns['design'])/max(comb,1)
    print(f"\n  design share: journal {dj:.1f}%  ->  combined {dc:.1f}%  "
          f"({dc-dj:+.1f} pp)")

    # ── duplication with the journal corpus ─────────────────────────────
    # Compare against the FULL journal retrieval (every journal article the
    # search returned), not just the final ai4chips corpus -- a conference
    # paper's journal extended version may sit anywhere in the retrieval.
    jtitles = {norm_title(r["title"]) for r in jrows}
    full_csv = Path(args.journaldir) / "raw_scopus_all.csv"
    if full_csv.exists():
        with open(full_csv, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = norm_title(r.get("title", ""))
                if t:
                    jtitles.add(t)
        print(f"\n[duplication baseline: {len(jtitles)} journal titles]")
    jtokens = {t: set(t.split()) for t in jtitles}
    exact = 0
    near = 0
    for r in kept:
        nt = norm_title(r["title"])
        if nt in jtitles:
            exact += 1
            continue
        toks = set(nt.split())
        if not toks:
            continue
        for jt, jtk in jtokens.items():
            inter = len(toks & jtk)
            union = len(toks | jtk)
            if union and inter / union >= 0.6:
                near += 1
                break
    print("\n" + "=" * 72)
    print("DUPLICATION WITH THE JOURNAL CORPUS")
    print("=" * 72)
    print(f"  exact title match          : {exact}")
    print(f"  near match (Jaccard >= 0.6): {near}")
    print(f"  total overlapping          : {exact + near} / {len(kept)} "
          f"({100.0*(exact+near)/max(len(kept),1):.1f}%)")

    # ── LLM temporal comparison (the reviewer's specific claim) ─────────
    print("\n" + "=" * 72)
    print("LLM-TAGGED PAPERS PER YEAR")
    print("=" * 72)
    jy = Counter(r["year"] for r in jrows
                 if "llm_foundation_models" in r["method_tags"])
    cy = defaultdict(Counter)
    for g, rs in groups.items():
        for r in rs:
            if "llm_foundation_models" in r["methods"]:
                cy[g][r["year"]] += 1
    years = sorted({*jy, *cy["EDA"], *cy["ML"]})
    print(f"  {'year':6}{'journal':>9}{'EDA conf':>11}{'ML conf':>10}")
    for y in years:
        print(f"  {y:6}{jy[y]:>9}{cy['EDA'][y]:>11}{cy['ML'][y]:>10}")


if __name__ == "__main__":
    main()
