"""Figure: citation distribution comparison — AI4chips vs full corpus."""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
from plot_style import (apply_style, save_figure, format_axes,
                        SINGLE_COL, COLORS, is_survey,
                        load_json_papers, load_jsonl_papers)

SURVEY_KW = ["survey", "review", "overview", "tutorial", "taxonomy"]


def main():
    apply_style()

    # ── Load AI4chips ────────────────────────────────────────────────────
    papers = load_json_papers()
    ai4 = sorted([int(p.get("cited_by_count") or 0)
                   for p in papers if not is_survey(p["title"])])

    # ── Load full corpus ─────────────────────────────────────────────────
    full = []
    for rec in load_jsonl_papers():
        entry = rec.get("entry", {})
        title = entry.get("dc:title", "")
        if any(kw in title.lower() for kw in SURVEY_KW):
            continue
        full.append(int(entry.get("citedby-count") or 0))
    full.sort()

    # ── Figure: 2-panel ──────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(SINGLE_COL * 2, 2.6))

    # --- Panel A: Empirical CDF ---
    for data, label, color in [
        (full, f"Full corpus (N={len(full):,})", COLORS[7]),
        (ai4,  f"AI4chips (N={len(ai4)})",       COLORS[0]),
    ]:
        arr = np.array(data)
        ecdf_y = np.arange(1, len(arr) + 1) / len(arr)
        ax1.step(arr, ecdf_y, where="post", color=color, linewidth=1.1,
                 label=label)

    ax1.set_xlim(0, 80)
    ax1.set_ylim(0, 1.02)
    ax1.set_xlabel("Citations")
    ax1.set_ylabel("Cumulative Fraction")
    ax1.set_title("(a) Citation CDF", fontsize=8)
    ax1.legend(fontsize=5.5, loc="lower right")
    # annotation: shift
    ax1.annotate("AI4chips curve\nshifted right\n(more highly cited)",
                 xy=(22, 0.72), fontsize=5.5, fontstyle="italic",
                 color=COLORS[0],
                 arrowprops=dict(arrowstyle="->", color=COLORS[0],
                                 linewidth=0.5),
                 xytext=(45, 0.55))
    format_axes(ax1)

    # --- Panel B: Paired bar — key percentiles ---
    labels = ["Mean", "Median", "P75", "P90", "% >= 10\ncites"]
    ai4_arr = np.array(ai4)
    full_arr = np.array(full)
    ai4_vals = [
        ai4_arr.mean(),
        np.median(ai4_arr),
        np.percentile(ai4_arr, 75),
        np.percentile(ai4_arr, 90),
        100 * np.sum(ai4_arr >= 10) / len(ai4_arr),
    ]
    full_vals = [
        full_arr.mean(),
        np.median(full_arr),
        np.percentile(full_arr, 75),
        np.percentile(full_arr, 90),
        100 * np.sum(full_arr >= 10) / len(full_arr),
    ]

    x = np.arange(len(labels))
    w = 0.35
    bars1 = ax2.bar(x - w / 2, ai4_vals, w, color=COLORS[0], label="AI4chips",
                     alpha=0.85)
    bars2 = ax2.bar(x + w / 2, full_vals, w, color=COLORS[7], label="Full corpus",
                     alpha=0.55)

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=6.5)
    ax2.set_ylabel("Value")
    ax2.set_title("(b) Key Metrics", fontsize=8)
    ax2.legend(fontsize=5.5, loc="upper left")
    format_axes(ax2)

    # value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            val = bar.get_height()
            fmt = f"{val:.0f}" if val >= 1 else f"{val:.1f}"
            ax2.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                     fmt, ha="center", va="bottom", fontsize=5.5)

    fig.tight_layout()
    save_figure(fig, "fig_cite_corpus_compare")


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--datadir", default=None,
                    help="Path to data directory (default: scopus_out7)")
    _args = _p.parse_args()
    if _args.datadir:
        from plot_style import set_data_dir
        set_data_dir(_args.datadir)
    main()
