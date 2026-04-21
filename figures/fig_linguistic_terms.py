"""Figures: Linguistic term trends in combined corpus + external references (~90k titles)."""

import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, MaxNLocator
import plot_style
from plot_style import (apply_style, save_figure, format_axes, SINGLE_COL,
                        COLORS, load_csv_papers)

# ── paths ────────────────────────────────────────────────────────────────
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "scopus_out10"
plot_style.set_data_dir(str(DATA))
CACHE_DIR = BASE / "scopus_out7" / "openalex_cache"  # one-off external refs cache


# ── data loading ─────────────────────────────────────────────────────────
def load_corpus_titles():
    """Return [{title, year}] for Scopus corpus only (N~4982)."""
    rows = []
    with open(DATA / "raw_scopus_all.jsonl") as f:
        for line in f:
            d = json.loads(line)
            e = d["entry"]
            title = (e.get("dc:title") or "").strip()
            year = d.get("year")
            if title and year:
                rows.append(dict(title=title, year=int(year)))
    return rows


def load_all_titles():
    """Return [{title, year}] for corpus + external references."""
    rows = load_corpus_titles()
    # external refs
    with open(CACHE_DIR / "ref_metadata_full.json") as f:
        meta = json.load(f)
    for info in meta.values():
        title = (info.get("title") or "").strip()
        year = info.get("year")
        if title and year and isinstance(year, int):
            rows.append(dict(title=title, year=int(year)))
    return rows


# ── terms ────────────────────────────────────────────────────────────────
BROAD_TERMS = {
    "learning":       r"\blearning\b",
    "neural":         r"\bneural\b",
}

METHOD_TERMS = {
    "machine learning":       r"\bmachine\s+learning\b",
    "deep learning":          r"\bdeep\s+learning\b",
    "reinforcement learning": r"\breinforcement\s+learning\b",
    "neural network":         r"\bneural\s+network",
    "GAN / adversarial":      r"\b(gan\b|adversarial)\b",
    "transformer":            r"\btransformer\b",
    "graph neural":           r"\bgraph\s+neural\b",
    "LLM / language model":   r"\b(llm|large\s+language\s+model|language\s+model)\b",
    "bayesian":               r"\bbayesian\b",
}


def count_terms(rows, terms, year_range):
    ymin, ymax = year_range
    papers_by_year = defaultdict(int)
    term_by_year = {t: defaultdict(int) for t in terms}

    for r in rows:
        y = r["year"]
        if y < ymin or y > ymax:
            continue
        papers_by_year[y] += 1
        tl = r["title"].lower()
        for name, pat in terms.items():
            if re.search(pat, tl):
                term_by_year[name][y] += 1

    years = list(range(ymin, ymax + 1))
    pct = {}
    for name in terms:
        pct[name] = [100 * term_by_year[name][y] / papers_by_year[y]
                     if papers_by_year[y] > 0 else 0 for y in years]
    n_papers = [papers_by_year[y] for y in years]
    return years, pct, n_papers


# ── figures ──────────────────────────────────────────────────────────────
def main():
    apply_style()
    rows = load_all_titles()
    print(f"  Loaded {len(rows):,} titles")

    # ── Figure 1: Broad terms 1985–2025 ──────────────────────────────────
    years, pct, n_papers = count_terms(rows, BROAD_TERMS, (1985, 2025))

    fig, ax1 = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(BROAD_TERMS):
        ax1.plot(years, pct[term], color=COLORS[i], linewidth=1.4,
                 marker="o", markersize=2.5, label=term, zorder=3)

    ax1.set_xlabel("Year")
    ax1.set_ylabel("Titles Containing Term (%)")
    ax1.set_title("Broad AI/ML Terms in Titles (N={:,})".format(sum(n_papers)))
    ax1.legend(fontsize=6.5, loc="upper left")
    ax1.xaxis.set_major_locator(MultipleLocator(5))
    ax1.set_xlim(1985, 2025)
    format_axes(ax1)
    fig.tight_layout()
    save_figure(fig, "fig_term_broad_trends")

    # ── Figure 2: Specific ML methods 1995–2025 ─────────────────────────
    years2, pct2, n_papers2 = count_terms(rows, METHOD_TERMS, (1995, 2025))

    # Two groups: established (pre-2015) and emerging (post-2015)
    established = ["neural network", "machine learning", "bayesian",
                   "GAN / adversarial"]
    emerging = ["deep learning", "reinforcement learning",
                "transformer", "graph neural", "LLM / language model"]

    # Fig 2a: established methods
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(established):
        ax.plot(years2, pct2[term], color=COLORS[i], linewidth=1.4,
                marker="o", markersize=2.5, label=term, zorder=3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("Established ML Terms (N={:,})".format(sum(n_papers2)))
    ax.legend(fontsize=6, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.set_xlim(1995, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_established")

    # Fig 2b: emerging methods (2010–2025 for clarity)
    years3, pct3, n_papers3 = count_terms(rows, METHOD_TERMS, (2010, 2025))

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(emerging):
        ax.plot(years3, pct3[term], color=COLORS[i], linewidth=1.4,
                marker="o", markersize=2.5, label=term, zorder=3)
    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("Emerging ML Terms (N={:,})".format(sum(n_papers3)))
    ax.legend(fontsize=6, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.set_xlim(2010, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_emerging")

    # ── Figure 3: All methods combined, stacked area 2000–2025 ───────────
    all_methods = {**METHOD_TERMS}  # exclude broad "learning"/"neural" to avoid double-counting
    years4, pct4, n_papers4 = count_terms(rows, all_methods, (2000, 2025))

    # Order by total area descending
    totals = {t: sum(pct4[t]) for t in all_methods}
    ordered = sorted(all_methods, key=lambda t: totals[t], reverse=True)

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 3.0))
    stacks = [pct4[t] for t in ordered]
    colors = COLORS[:len(ordered)]

    ax.stackplot(years4, *stacks, labels=ordered, colors=colors, alpha=0.82)
    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("ML Terminology Landscape (N={:,})".format(sum(n_papers4)))
    ax.legend(fontsize=5.5, loc="upper left", ncol=2)
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.set_xlim(2000, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_landscape")

    # ── Figure 4: Paper volume context (secondary) ───────────────────────
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.2))
    ax.bar(years, n_papers, color=COLORS[0], width=0.7, alpha=0.7)
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Titles")
    ax.set_title("Combined Dataset Volume")
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.set_xlim(1985, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_volume")

    # ── Figure 5: Terminological specialization 2000–2025 ─────────────
    # "Any ML/AI term" = title contains broad OR specific term
    # "Specific method named" = title contains at least one named method
    # Gap = generic-only titles (broad term but no specific method)
    all_pats_broad = [re.compile(p, re.IGNORECASE) for p in BROAD_TERMS.values()]
    all_pats_specific = [re.compile(p, re.IGNORECASE) for p in METHOD_TERMS.values()]

    yr_min, yr_max = 2000, 2025
    papers_by_year = defaultdict(int)
    any_ml_by_year = defaultdict(int)
    specific_by_year = defaultdict(int)

    for r in rows:
        y = r["year"]
        if y < yr_min or y > yr_max:
            continue
        papers_by_year[y] += 1
        tl = r["title"].lower()
        has_broad = any(p.search(tl) for p in all_pats_broad)
        has_specific = any(p.search(tl) for p in all_pats_specific)
        if has_broad or has_specific:
            any_ml_by_year[y] += 1
        if has_specific:
            specific_by_year[y] += 1

    spec_years = list(range(yr_min, yr_max + 1))
    any_ml_pct = [100 * any_ml_by_year[y] / papers_by_year[y]
                  if papers_by_year[y] > 0 else 0 for y in spec_years]
    specific_pct = [100 * specific_by_year[y] / papers_by_year[y]
                    if papers_by_year[y] > 0 else 0 for y in spec_years]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    ax.fill_between(spec_years, specific_pct, any_ml_pct,
                    color=COLORS[0], alpha=0.15, label="generic only")
    ax.plot(spec_years, any_ml_pct, color=COLORS[0], linewidth=1.4,
            marker="o", markersize=2.5, label="any ML/AI term", zorder=3)
    ax.plot(spec_years, specific_pct, color=COLORS[1], linewidth=1.4,
            marker="s", markersize=2.5, label="specific method named", zorder=3)

    # annotate the gap at a year where it's wide enough to read
    mid_yr = 2018
    mid_idx = mid_yr - yr_min
    gap_y = (any_ml_pct[mid_idx] + specific_pct[mid_idx]) / 2
    ax.annotate("generic\nonly", xy=(mid_yr, gap_y), fontsize=6,
                ha="center", va="center", color=COLORS[0], alpha=0.8)

    ax.set_xlabel("Year")
    ax.set_ylabel("Share of Titles (%)")
    n_total = sum(papers_by_year[y] for y in spec_years)
    ax.set_title("Terminological Specialization (N={:,})".format(n_total))
    ax.legend(fontsize=6, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.set_xlim(yr_min, yr_max)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_specialization")

    # ── Figure 6: Broad terms in SLR corpus only (%, 2015–2025) ────────
    corpus_rows = load_corpus_titles()
    n_corpus = len(corpus_rows)
    print(f"  Corpus-only titles: {n_corpus:,}")
    yrs_c, pct_c, npc = count_terms(corpus_rows, BROAD_TERMS, (2015, 2025))

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(BROAD_TERMS):
        ax.plot(yrs_c, pct_c[term], color=COLORS[i], linewidth=1.4,
                marker="o", markersize=3, label=f'"{term}"', zorder=3)

    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("Broad Terms in SLR Corpus (N={:,})".format(sum(npc)))
    ax.legend(fontsize=6.5, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.set_xlim(2015, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_keyword_trends_pct")

    # ── Figure 7: Broad terms in ai4chips subset (%, 2018–2025) ────────
    ai4_papers = load_csv_papers()
    ai4_rows = [dict(title=p["title"], year=p["year"]) for p in ai4_papers]
    n_ai4 = len(ai4_rows)
    print(f"  AI4chips titles: {n_ai4:,}")
    yrs_a, pct_a, npa = count_terms(ai4_rows, BROAD_TERMS, (2018, 2025))

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(BROAD_TERMS):
        ax.plot(yrs_a, pct_a[term], color=COLORS[i], linewidth=1.4,
                marker="o", markersize=3, label=f'"{term}"', zorder=3)

    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("Broad Terms in AI for Chips (N={:,})".format(sum(npa)))
    ax.legend(fontsize=6.5, loc="upper left")
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.set_xlim(2018, 2025)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_keyword_trends_ai4chips")

    # ── Figure 8: Method-name crossover (extended corpus, 2015–2024) ───
    # Stop at 2024 — 2025 reference coverage is thin and creates artifact dip
    CROSSOVER_TERMS = {
        "machine learning":       r"\bmachine\s+learning\b",
        "deep learning":          r"\bdeep\s+learning\b",
        "reinforcement learning": r"\breinforcement\s+learning\b",
        "transformer":            r"\btransformer\b",
        "GNN":                    r"\bgraph\s+neural\b",
        "LLM":                    r"\b(llm|large\s+language\s+model|language\s+model)\b",
    }
    yrs_x, pct_x, npx = count_terms(rows, CROSSOVER_TERMS, (2015, 2024))

    # Two groups: declining umbrella vs rising specific
    umbrella = ["machine learning", "deep learning"]
    specific = ["reinforcement learning", "transformer", "GNN", "LLM"]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.8))
    for i, term in enumerate(umbrella):
        ax.plot(yrs_x, pct_x[term], color=COLORS[i], linewidth=1.4,
                marker="o", markersize=2.5, label=term, zorder=3)
    for i, term in enumerate(specific):
        ax.plot(yrs_x, pct_x[term], color=COLORS[i + 2], linewidth=1.4,
                marker="s", markersize=2.5, linestyle="--", label=term, zorder=3)

    ax.set_xlabel("Year")
    ax.set_ylabel("Titles Containing Term (%)")
    ax.set_title("Method-Name Crossover (N={:,})".format(sum(npx)))
    ax.legend(fontsize=5.5, loc="upper left", ncol=2)
    ax.xaxis.set_major_locator(MultipleLocator(2))
    ax.set_xlim(2015, 2024)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_term_crossover")


if __name__ == "__main__":
    main()
