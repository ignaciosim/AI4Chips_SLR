"""Figure + table: title keyword frequency across top 10 countries (full corpus).

Reads raw_scopus_all.jsonl. For each paper, extracts unique title words
(lowercased, length >= 3, stopwords removed), groups by affiliation country.
Outputs:
  1. Printed pivoted table (keywords × countries, % of that country's papers)
  2. Heatmap figure (top 15 keywords × top 10 countries)
"""

import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from plot_style import (apply_style, save_figure, SINGLE_COL, COLORS,
                        load_jsonl_papers)

STOP = set(
    "a an the of for in on to and with by from is at as its into that this "
    "using based via their are be can or was it which has been have not but "
    "also than more between through over under about after all both each "
    "during other such when how two new we our they will any may do used".split()
)

N_COUNTRIES = 10
N_KEYWORDS = 15


def _extract_words(title):
    """Return set of non-stop words (len >= 3) from a title."""
    return {w for w in re.findall(r"[a-z]+", title.lower()) if len(w) >= 3 and w not in STOP}


def main():
    apply_style()
    papers = load_jsonl_papers()

    country_word = defaultdict(Counter)  # country -> {word: paper_count}
    country_n = Counter()                # country -> total papers

    for rec in papers:
        entry = rec.get("entry", {})
        title = (entry.get("dc:title") or "").strip()
        if not title:
            continue

        affiliations = entry.get("affiliation") or []
        countries = set()
        for a in affiliations:
            c = a.get("affiliation-country", "")
            if c:
                countries.add(c)
        if not countries:
            continue

        words = _extract_words(title)
        for c in countries:
            country_n[c] += 1
            country_word[c].update(words)

    top_countries = [c for c, _ in country_n.most_common(N_COUNTRIES)]

    # Union of top keywords across all top countries, ranked by global count
    global_word = Counter()
    for c in top_countries:
        for w, cnt in country_word[c].items():
            global_word[w] += cnt
    top_keywords = [w for w, _ in global_word.most_common(N_KEYWORDS)]

    # ── Table ──────────────────────────────────────────────────────────────
    short = {
        "United States": "US",
        "South Korea": "S.Korea",
        "Germany": "Germany",
        "France": "France",
        "Taiwan": "Taiwan",
        "Canada": "Canada",
        "Japan": "Japan",
        "China": "China",
        "India": "India",
        "Iran": "Iran",
    }

    hdr_names = [short.get(c, c[:8]) for c in top_countries]
    col_w = 9
    print(f"\nTitle keyword frequency by country (% of country's papers)")
    print(f"{'Keyword':<16}" + "".join(f"{h:>{col_w}}" for h in hdr_names))
    print("-" * (16 + col_w * N_COUNTRIES))
    for w in top_keywords:
        row = f"{w:<16}"
        for c in top_countries:
            n = country_n[c]
            cnt = country_word[c].get(w, 0)
            pct = 100 * cnt / n if n else 0
            row += f"{pct:>{col_w - 1}.1f}%" if cnt > 0 else f"{'—':>{col_w}}"
        print(row)
    # footer: N
    print("-" * (16 + col_w * N_COUNTRIES))
    print(f"{'N':<16}" + "".join(f"{country_n[c]:>{col_w}}" for c in top_countries))
    print()

    # ── Heatmap figure ─────────────────────────────────────────────────────
    matrix = np.zeros((N_KEYWORDS, N_COUNTRIES))
    for i, w in enumerate(top_keywords):
        for j, c in enumerate(top_countries):
            n = country_n[c]
            matrix[i, j] = 100 * country_word[c].get(w, 0) / n if n else 0

    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 1.2))

    cmap = LinearSegmentedColormap.from_list("wb", ["#FFFFFF", COLORS[0]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0)

    ax.set_xticks(range(N_COUNTRIES))
    ax.set_xticklabels([short.get(c, c[:8]) for c in top_countries],
                       rotation=45, ha="right", fontsize=6)
    ax.set_yticks(range(N_KEYWORDS))
    ax.set_yticklabels(top_keywords, fontsize=6.5)

    for i in range(N_KEYWORDS):
        for j in range(N_COUNTRIES):
            val = matrix[i, j]
            if val >= 1.0:
                color = "white" if val > 12 else "black"
                ax.text(j, i, f"{val:.0f}", ha="center", va="center",
                        fontsize=5, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.03)
    cbar.set_label("% of papers", fontsize=6.5)
    cbar.ax.tick_params(labelsize=5.5)

    ax.set_title("Title Keywords by Country", fontsize=8)
    fig.tight_layout()
    save_figure(fig, "fig_keyword_country")


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
