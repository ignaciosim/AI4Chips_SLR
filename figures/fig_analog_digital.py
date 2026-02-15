"""Figure: Analog vs Digital — separate single-column plots for donut and trends."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, load_csv_papers, classify_analog_digital)

CATEGORIES = ["digital", "analog", "both", "domain-agnostic"]
CAT_DISPLAY = {
    "analog": "Analog",
    "digital": "Digital",
    "both": "Both",
    "domain-agnostic": "Domain-Agnostic",
}
CAT_COLORS = {
    "digital": COLORS[0],
    "analog": COLORS[1],
    "both": COLORS[2],
    "domain-agnostic": COLORS[9],  # gray
}


def main():
    apply_style()
    papers = load_csv_papers()

    cat_counts = Counter()
    papers_by_year = Counter()
    cat_year = defaultdict(Counter)
    for p in papers:
        papers_by_year[p["year"]] += 1
        cat = classify_analog_digital(p["chip_tasks"], p["title"])
        cat_counts[cat] += 1
        cat_year[cat][p["year"]] += 1

    all_years = sorted(papers_by_year)

    # ── Donut chart ────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.0))
    sizes = [cat_counts[c] for c in CATEGORIES]
    labels = [f"{CAT_DISPLAY[c]}\n({cat_counts[c]}, {100*cat_counts[c]/len(papers):.0f}%)"
              for c in CATEGORIES]
    colors = [CAT_COLORS[c] for c in CATEGORIES]

    wedges, texts = ax.pie(sizes, labels=labels, colors=colors,
                            startangle=90, wedgeprops=dict(width=0.45),
                            textprops={"fontsize": 7})
    ax.set_title("Domain Split", pad=12)
    fig.tight_layout()
    save_figure(fig, "fig_analog_digital_donut")

    # ── Stacked bar over time ──────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.0))
    x = np.arange(len(all_years))
    width = 0.7
    bottoms = np.zeros(len(all_years))
    for cat in CATEGORIES:
        vals = np.array([cat_year[cat].get(y, 0) for y in all_years])
        ax.bar(x, vals, width, bottom=bottoms, label=CAT_DISPLAY[cat],
               color=CAT_COLORS[cat])
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Domain Composition Over Time")
    ax.legend(fontsize=6.5, ncol=1)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_analog_digital_trends")


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
