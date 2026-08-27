#!/usr/bin/env python3
"""fig_method_stage_time.py — how method use per lifecycle stage has changed.

`fig_method_stage.py` averages over the whole window, which dilutes anything
recent: foundation models are 15% of design papers across 2015-2025 but 37% of
design papers published in 2025, because eight of those years predate the
method entirely. This figure adds the time dimension.

  (a) Method share within each stage over the RECENT period -- what the field
      is using now.
  (b) Change in share from the earlier period, in percentage points -- what is
      rising and falling, and where.

Period labels are computed from the corpus, not hardcoded. This is an
AGGREGATE, so it uses the whole corpus including the partially-indexed final
year; only time-series figures apply plot_style.DISPLAY_YEAR_MAX.

A two-period split rather than per-year lines: packaging and transit hold
single-digit paper counts per year, so annual series there would be noise.
Even pooled they are small (packaging 9 -> 22, transit 15 -> 11 papers), so
those columns are marked; a swing of one or two papers moves them by tens of
points.

Panel (b) uses a diverging scale with a neutral midpoint, since the quantity
has a meaningful zero and a sign. Panel (a) is sequential: it is a magnitude.

Usage:
    python3 figures/fig_method_stage_time.py --datadir scopus_out12
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style  # noqa: E402
from plot_style import (display_methods,
                        apply_style, save_figure, load_csv_papers,  # noqa: E402
                        DOUBLE_COL, COLORS)

STAGES = ["design", "fabrication", "packaging", "transit", "in_field"]
LABEL = {"design": "Design", "fabrication": "Fabrication",
         "packaging": "Packaging", "transit": "Transit",
         "in_field": "In-field"}
SPLIT_YEAR = 2023          # first year of the "recent" period
MIN_STAGE_N = 25           # below this, mark the column as small-sample
MIN_METHOD_TOTAL = 8       # drop long-tail families


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default=None)
    args = ap.parse_args()
    if args.datadir:
        plot_style.set_data_dir(args.datadir)

    # Aggregate, not a time series: year_max=None keeps the whole curated
    # corpus including the partially-indexed final year. Period labels are
    # derived from the data rather than hardcoded, so they cannot drift out of
    # step with the corpus.
    papers = load_csv_papers(year_max=None)
    early, late = defaultdict(list), defaultdict(list)
    totals = Counter()
    for p in papers:
        if p["stage"] not in STAGES:
            continue
        (late if p["year"] >= SPLIT_YEAR else early)[p["stage"]].append(p)
        for m in display_methods(p["method_tags"]):
            totals[m] += 1

    methods = sorted([m for m, c in totals.items() if c >= MIN_METHOD_TOTAL],
                     key=lambda m: -totals[m])

    yrs = [p["year"] for p in papers if p["stage"] in STAGES]
    y_min, y_max = min(yrs), max(yrs)
    LATE = f"{SPLIT_YEAR}\u2013{y_max}"
    EARLY = f"{y_min}\u2013{SPLIT_YEAR - 1}"

    def share(group, stage, method):
        g = group.get(stage, [])
        if not g:
            return np.nan
        return 100.0 * sum(1 for p in g if method in p["method_tags"]) / len(g)

    lvl = np.array([[share(late, s, m) for s in STAGES] for m in methods])
    chg = np.array([[share(late, s, m) - share(early, s, m) for s in STAGES]
                    for m in methods])

    apply_style()
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(DOUBLE_COL, 4.0))

    # ── (a) recent levels: sequential, one hue ──────────────────────────
    seq = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(lvl, aspect="auto", cmap=seq, vmin=0)
    vmax = np.nanmax(lvl)
    for i in range(len(methods)):
        for j in range(len(STAGES)):
            v = lvl[i, j]
            if not np.isnan(v) and v > 0:
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=5.5,
                        color="white" if v > vmax * 0.55 else "#222222")
    ax.set_title(f"(a) Share within stage, {LATE} (%)", fontsize=8.5)

    # ── (b) change: diverging, neutral midpoint ─────────────────────────
    div = LinearSegmentedColormap.from_list(
        "div", [COLORS[1], "#F7F7F7", COLORS[0]])          # fall / none / rise
    lim = np.nanmax(np.abs(chg))
    im2 = ax2.imshow(chg, aspect="auto", cmap=div,
                     norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim))
    for i in range(len(methods)):
        for j in range(len(STAGES)):
            v = chg[i, j]
            if not np.isnan(v):
                ax2.text(j, i, f"{v:+.0f}", ha="center", va="center",
                         fontsize=5.5,
                         color="white" if abs(v) > lim * 0.62 else "#222222")
    ax2.set_title(f"(b) Change vs {EARLY} (pp)", fontsize=8.5)

    for a, image, cl in ((ax, im, "% of stage's papers"),
                         (ax2, im2, "percentage points")):
        a.set_xticks(range(len(STAGES)))
        a.set_xticklabels(
            [LABEL[s] + ("*" if len(late.get(s, [])) < MIN_STAGE_N else "")
             for s in STAGES], rotation=45, ha="right", fontsize=7)
        a.set_yticks(range(len(methods)))
        a.set_yticklabels([m.replace("_", " ") for m in methods], fontsize=7)
        for sp in a.spines.values():
            sp.set_visible(False)
        a.tick_params(length=0)
        cb = fig.colorbar(image, ax=a, shrink=0.82, pad=0.02)
        cb.set_label(cl, fontsize=6.5)
        cb.ax.tick_params(labelsize=6)
        cb.outline.set_visible(False)
    ax2.set_yticklabels([])

    small = [LABEL[s] for s in STAGES if len(late.get(s, [])) < MIN_STAGE_N]
    if small:
        fig.text(0.01, 0.015,
                 "* fewer than %d papers in the recent period (%s): a shift of "
                 "one or two papers moves these columns by tens of points."
                 % (MIN_STAGE_N, ", ".join(small)),
                 fontsize=5.8, color="#777777")

    fig.tight_layout(rect=(0, 0.045, 1, 1), w_pad=1.0)
    save_figure(fig, "fig_method_stage_time")

    print("papers per stage  early -> late:")
    for s in STAGES:
        print(f"  {s:13}{len(early.get(s, [])):>4} -> {len(late.get(s, [])):<4}")


if __name__ == "__main__":
    main()
