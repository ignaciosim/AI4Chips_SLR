"""Figure: Emerging topics — grouped bar for soft error and deposition over time."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from plot_style import (apply_style, save_figure, format_axes, DOUBLE_COL,
                        COLORS, load_csv_papers, matches_topic,
                        SOFT_ERROR_KW, SOFT_ERROR_EXCLUDE, DEPOSITION_KW)

TOPICS = {
    "soft_error": {
        "label": "Soft/Silent Error",
        "kw": SOFT_ERROR_KW,
        "exclude": SOFT_ERROR_EXCLUDE,
    },
    "deposition": {
        "label": "Deposition Opt.",
        "kw": DEPOSITION_KW,
        "exclude": None,
    },
}


def main():
    apply_style()
    papers = load_csv_papers()

    papers_by_year = Counter()
    topic_year = defaultdict(Counter)

    for p in papers:
        papers_by_year[p["year"]] += 1
        title_lower = p["title"].lower()
        for key, tdef in TOPICS.items():
            if matches_topic(title_lower, tdef["kw"], tdef["exclude"]):
                topic_year[key][p["year"]] += 1

    all_years = sorted(papers_by_year)

    fig, ax = plt.subplots(figsize=(DOUBLE_COL * 0.6, 3.0))

    x = np.arange(len(all_years))
    width = 0.35

    keys = ["soft_error", "deposition"]
    for i, key in enumerate(keys):
        vals = [topic_year[key].get(y, 0) for y in all_years]
        bars = ax.bar(x + i * width, vals, width, label=TOPICS[key]["label"],
                      color=COLORS[i])
        # Add count labels on non-zero bars
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                        str(val), ha="center", va="bottom", fontsize=6.5)

    ax.set_xticks(x + width / 2)
    ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right")
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("Emerging Topics Over Time")
    ax.legend(fontsize=7)
    format_axes(ax)

    fig.tight_layout()
    save_figure(fig, "fig_emerging_topics")


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
