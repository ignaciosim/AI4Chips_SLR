#!/usr/bin/env python3
"""fig_cross_stage.py — Cross-stage coupling across the silicon lifecycle.

Answers the reviewer request for a quantitative test of the "siloed lifecycle"
claim (a stage-to-stage matrix rather than an inference from absent papers).

Signal: a paper retrieved by more than one lifecycle phase query has matched
the search vocabulary of two stages. `merge_scopus.py` deduplicates each paper
to a single stage, but the per-stage `raw_scopus_*.jsonl` files still record
every phase that hit it, so the multi-stage membership is recoverable.

IMPORTANT: this is a symmetric co-occurrence measure, not directed information
flow. It bounds cross-stage work from above — a paper can share two stages'
vocabulary without moving data between them. The caption must say so.

Panel (a) lower-triangle matrix of raw counts: papers matching both stages.
Panel (b) how many stages a single paper spans.

ON THE NULL MODEL, and why it is not reported in the paper. Raw counts scale
with stage size, so they cannot be read directly as coupling strength. We
therefore tested them against a configuration null (each paper keeps its own
stage count; which stages it gets are redrawn with probability proportional to
stage size). Under that null design-involving pairs come out below expectation
(0.85x) and post-design pairs above it (1.32x), both significant in aggregate.
BUT running the identical test on the full 14,551-record screened corpus -- most
of which is not AI-for-chips work -- gives 0.63x and 1.36x. The asymmetry is a
property of the surrounding chip literature, not of AI-for-chips research, and
AI work is in fact LESS design-siloed than its surroundings. The analysis is
kept here as a diagnostic (printed to stdout) but the paper reports only the
descriptive results, which do not depend on it.

Usage:
    python3 figures/fig_cross_stage.py --datadir scopus_out12
"""
import argparse
import collections
import itertools
import json
import random
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style  # noqa: E402
from plot_style import (apply_style, save_figure, format_axes,  # noqa: E402
                        load_csv_papers, DOUBLE_COL, COLORS)

STAGES = ["design", "fabrication", "packaging", "transit", "in_field",
          "disposal"]
# An observed/expected ratio on one or two papers is not estimable -- the
# in-field/disposal cell holds a single paper and would otherwise read as the
# most strongly coupled pair in the matrix. Below this count the cell is drawn
# neutral and its count alone is reported.
MIN_OBS_FOR_RATIO = 3
RATIO_VMAX = 2.0
# Null model. An independence null (expected = n_a*n_b/N) is WRONG here: it
# lets a paper belong to any number of stages, predicting 379 co-occurring
# pairs when only 204 are structurally possible given that 77% of papers match
# exactly one stage. Under it every pair trivially falls "below chance". We
# instead use a configuration null that keeps each paper's OWN stage count and
# draws which stages it gets with probability proportional to stage size.
NULL_REPS = 2000
NULL_SEED = 11
POST_DESIGN = ("fabrication", "packaging", "transit", "in_field")
LABEL = {"design": "Design", "fabrication": "Fabrication",
         "packaging": "Packaging", "transit": "Transit",
         "in_field": "In-field", "disposal": "Disposal"}


def phase_membership(datadir):
    """{eid: {stage, ...}} — every phase query that retrieved each record."""
    hits = collections.defaultdict(set)
    for path in Path(datadir).glob("raw_scopus_*.jsonl"):
        if path.name == "raw_scopus_all.jsonl":   # merge output, not a query
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                eid = (rec.get("entry") or {}).get("eid")
                if eid:
                    hits[eid].add(rec.get("stage"))
    return hits


def build(datadir):
    memb = phase_membership(datadir)
    hits = memb
    # Aggregate over the whole curated corpus: year_max=None keeps the
    # partially-indexed final year (this is not a time series), and the
    # loader's default curation matches the corpus size reported in the text.
    papers = load_csv_papers(year_max=None)
    pair = collections.Counter()
    diag = collections.Counter()
    span = collections.Counter()
    for p in papers:
        s = sorted(hits.get(p["doc_id"], set()) & set(STAGES))
        span[len(s)] += 1
        for a in s:
            diag[a] += 1
        for a, b in itertools.combinations(s, 2):
            pair[(a, b)] += 1
            pair[(b, a)] += 1
    n = len(papers)

    # ── configuration null ──────────────────────────────────────────────
    sets = [sorted(memb.get(p["doc_id"], set()) & set(STAGES)) for p in papers]
    sets = [s for s in sets if s]
    weights = [diag[s] for s in STAGES]
    rng = random.Random(NULL_SEED)

    def _draw(k):
        pool, w, pick = list(STAGES), list(weights), []
        for _ in range(k):
            tot = sum(w)
            r, acc = rng.random() * tot, 0.0
            i = 0
            for i, wt in enumerate(w):
                acc += wt
                if r <= acc:
                    break
            pick.append(pool.pop(i))
            w.pop(i)
        return pick

    null = collections.defaultdict(list)
    agg_design, agg_post = [], []
    for _ in range(NULL_REPS):
        c = collections.Counter()
        d = q = 0
        for st in sets:
            for a, b in itertools.combinations(sorted(_draw(len(st))), 2):
                c[(a, b)] += 1
                if "design" in (a, b):
                    d += 1
                elif a in POST_DESIGN and b in POST_DESIGN:
                    q += 1
        for ab in itertools.combinations(STAGES, 2):
            # keys must be sorted: `c` above is built from sorted pairs, and
            # STAGES order is not alphabetical (in_field precedes packaging and
            # transit alphabetically but follows them in STAGES). Looking up an
            # unsorted key silently returned 0 for every permutation.
            null[tuple(sorted(ab))].append(c.get(tuple(sorted(ab)), 0))
        agg_design.append(d)
        agg_post.append(q)

    ratio, pval = {}, {}
    for a, b in itertools.combinations(STAGES, 2):
        vals = null[tuple(sorted((a, b)))]
        mu = sum(vals) / len(vals)
        obs = pair.get((a, b), 0)
        r = (obs / mu) if mu > 0 else float("nan")
        ge = sum(1 for v in vals if v >= obs)
        le = sum(1 for v in vals if v <= obs)
        pv = min(1.0, 2 * min(ge, le) / len(vals))
        ratio[(a, b)] = ratio[(b, a)] = r
        pval[(a, b)] = pval[(b, a)] = pv

    # aggregate contrast: design-involving vs post-design-only pairs
    obs_d = sum(pair.get(tuple(sorted(("design", s))), 0)
                for s in STAGES if s != "design")
    obs_q = sum(pair.get(tuple(sorted((a, b))), 0)
                for a, b in itertools.combinations(POST_DESIGN, 2))
    agg = {
        "design_obs": obs_d,
        "design_null": sum(agg_design) / len(agg_design),
        "design_p": (sum(1 for v in agg_design if v <= obs_d) + 1) / (NULL_REPS + 1),
        "post_obs": obs_q,
        "post_null": sum(agg_post) / len(agg_post),
        "post_p": (sum(1 for v in agg_post if v >= obs_q) + 1) / (NULL_REPS + 1),
    }
    return pair, diag, span, n, ratio, pval, agg


def main(datadir=None):
    # No argv parsing here: generate_all_figures.py imports this module and
    # calls main() directly, so anything read from sys.argv would see the
    # runner's own flags (--only, ...) and abort the whole run.
    if datadir:
        plot_style.set_data_dir(datadir)
    datadir = plot_style.DATA_DIR

    pair, diag, span, n, ratio, pval, agg = build(datadir)
    apply_style()

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(DOUBLE_COL, 3.5),
        gridspec_kw={"width_ratios": [1.45, 1]})

    # ── panel (a): lower-triangle co-occurrence matrix ──────────────────
    k = len(STAGES)
    m = np.full((k, k), np.nan)
    for i, a in enumerate(STAGES):
        for j, b in enumerate(STAGES):
            if i > j:                      # lower triangle only (symmetric)
                m[i, j] = pair.get((a, b), 0)

    # Sequential shading on the raw count. Counts scale with stage size, so
    # the caption must say they are not a measure of coupling strength.
    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    cmap.set_bad("none")
    vmax = np.nanmax(m) if np.isfinite(m).any() else 1
    im = ax.imshow(m, cmap=cmap, vmin=0, vmax=vmax)

    for i in range(k):
        for j in range(k):
            if i > j:
                v = int(m[i, j])
                ax.text(j, i, str(v), ha="center", va="center", fontsize=7,
                        color="white" if v > vmax * 0.55 else "#222222")
            elif i == j:
                # stage total — neutral, deliberately outside the colour scale
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1,
                                           facecolor="#EDEDED",
                                           edgecolor="white", lw=1.5))
                ax.text(j, i, str(diag.get(STAGES[i], 0)), ha="center",
                        va="center", fontsize=7, color="#555555",
                        style="italic")

    ax.set_xticks(range(k)); ax.set_yticks(range(k))
    ax.set_xticklabels([LABEL[s] for s in STAGES], rotation=45, ha="right")
    ax.set_yticklabels([LABEL[s] for s in STAGES])
    ax.set_xticks(np.arange(-.5, k, 1), minor=True)
    ax.set_yticks(np.arange(-.5, k, 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.5)
    ax.tick_params(which="minor", length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("(a) Stage co-occurrence\n(italic diagonal: papers per stage)",
                 fontsize=8.5, pad=6)
    cb = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.03)
    cb.set_label("papers matching both stages", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_visible(False)

    # ── panel (b): how many stages one paper spans ──────────────────────
    cats = [1, 2, 3, 4]
    vals = [span.get(c, 0) for c in cats[:3]] + \
           [sum(v for c, v in span.items() if c >= 4)]
    pct = [100.0 * v / n for v in vals]
    # Span count is ORDINAL, not categorical: one hue, not three. The empty
    # 4+ bar is greyed because it is the notable absence, not another series.
    bars = ax2.bar([str(c) if c < 4 else "4+" for c in cats], pct,
                   color=[COLORS[0], COLORS[0], COLORS[0], "#BBBBBB"],
                   width=0.62)
    for b, v, p in zip(bars, vals, pct):
        ax2.text(b.get_x() + b.get_width() / 2, p + 1.5,
                 f"{p:.1f}%\n(n={v})", ha="center", va="bottom", fontsize=7,
                 color="#222222")
    ax2.set_ylim(0, max(pct) * 1.32)
    ax2.set_xlabel("Lifecycle stages spanned")
    ax2.set_ylabel("Share of corpus (%)")
    ax2.set_title("(b) Lifecycle span per paper\n ", fontsize=8.5, pad=6)
    format_axes(ax2)

    fig.text(0.005, 0.014,
             "Counts scale with stage size and are not a measure of coupling "
             "strength: the largest stages necessarily share the most papers.",
             fontsize=5.8, color="#777777")
    fig.tight_layout(rect=(0, 0.045, 1, 1), w_pad=1.6)
    save_figure(fig, "fig_cross_stage")

    print(f"corpus N={n}")
    print(f"  span distribution: "
          f"{ {c: span.get(c, 0) for c in sorted(span)} }")
    linked = sum(1 for a, b in itertools.combinations(STAGES, 2)
                 if pair.get((a, b), 0))
    print(f"  stage pairs with >=1 bridging paper: {linked}/15")
    print("  [diagnostic only, not reported in the paper]")
    print("  observed / null expectation by pair (configuration null):")
    for a, b in sorted(itertools.combinations(STAGES, 2),
                       key=lambda ab: -pair.get(ab, 0)):
        o = pair.get((a, b), 0)
        if o:
            print(f"    {a:12}+ {b:12} obs={o:>3}  ratio={ratio[(a, b)]:.2f}"
                  f"  p={pval[(a, b)]:.3f}")
    print(f"  AGGREGATE  design-involving: {agg['design_obs']} vs "
          f"{agg['design_null']:.1f} (p={agg['design_p']:.4f})")
    print(f"             post-design only: {agg['post_obs']} vs "
          f"{agg['post_null']:.1f} (p={agg['post_p']:.4f})")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser()
    _ap.add_argument("--datadir", default=None)
    main(_ap.parse_args().datadir)
