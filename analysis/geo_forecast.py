#!/usr/bin/env python3
"""
Country-level forecasting for AI-for-Chips contributions.

For the top-N contributing countries, fits:
  - Exponential trend on absolute yearly counts  → CAGR, projected counts
  - Linear trend on yearly share (%) of the corpus → share trajectory, projected share

Fit window is 2015–2025 (11 complete years); 2026 is excluded from fits
because the year is partial (indexing still in progress).

Outputs:
  scopus_out10/geo_forecast.csv
  scopus_out10/geo_forecast.md
  scopus_out10/figures/fig_geo_forecast_counts.{pdf,png}
  scopus_out10/figures/fig_geo_forecast_share.{pdf,png}

Usage:
  python3 analysis/geo_forecast.py --datadir scopus_out10 --top 5
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# Shared plotting style
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style
from plot_style import (apply_style, save_figure, format_axes,
                        SINGLE_COL, DOUBLE_COL, COLORS, EUROPE)


FIT_START = 2015
FIT_END = 2025       # inclusive; last complete year
PROJECT_TO = 2030    # inclusive; projected range 2026–2030

# Non-overlapping halves of the fit window, for phase-shift comparison.
P1_RANGE = range(2015, 2021)   # 2015–2020 inclusive (6 years)
P2_RANGE = range(2021, 2026)   # 2021–2025 inclusive (5 years)


def exp_model(t, a, b):
    return a * np.exp(b * t)


def fit_exponential(years, counts):
    """Fit y = a*exp(b*t) to (years, counts) with t = years - FIT_START.
    Returns dict with a, b, CAGR, R²; None if fit fails."""
    from scipy.optimize import curve_fit
    y = np.asarray(counts, dtype=float)
    if y.sum() < 3 or (y > 0).sum() < 4:
        return None  # too sparse
    t = np.asarray(years, dtype=float) - FIT_START
    try:
        popt, _ = curve_fit(exp_model, t, y, p0=[max(y[0], 0.5), 0.1],
                            maxfev=10000, bounds=([0, -2], [1000, 2]))
    except Exception:
        return None
    a, b = popt
    pred = exp_model(t, *popt)
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {"a": float(a), "b": float(b), "cagr": float(np.exp(b) - 1), "r2": float(r2)}


def fit_linear(years, values):
    """Least-squares linear fit. Returns dict with slope, intercept, R²."""
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 3:
        return None
    m, b = np.polyfit(x, y, 1)
    pred = m * x + b
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {"slope": float(m), "intercept": float(b), "r2": float(r2)}


def load_country_year_matrix(json_path):
    """Return (years, country -> {year: count}, total_by_year, europe_members).
    Adds a synthetic 'Europe' aggregate covering all countries in plot_style.EUROPE.
    Returns the set of European countries actually observed, for drill-down."""
    data = json.loads(Path(json_path).read_text())
    country_year = defaultdict(Counter)
    total_by_year = Counter()
    europe_members = Counter()  # members_observed -> paper count
    years = set()
    for p in data:
        year = int(p["year"])
        years.add(year)
        affils = p.get("affiliations") or []
        countries = {a.get("affiliation-country", "") for a in affils}
        countries = {c for c in countries if c}
        if not countries:
            continue
        # Per-country counts
        for c in countries:
            country_year[c][year] += 1
            if c in EUROPE:
                europe_members[c] += 1
        # Europe-bloc count: the paper is counted for Europe if ANY
        # affiliation country is in EUROPE (matches any-affiliation rule).
        if any(c in EUROPE for c in countries):
            country_year["Europe"][year] += 1
        total_by_year[year] += 1
    return sorted(years), country_year, total_by_year, europe_members


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out10")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    outdir = Path(args.datadir)
    json_path = outdir / "final_ai4chips_high_only.json"
    years, country_year, total_by_year, europe_members = load_country_year_matrix(json_path)

    # Rank candidates by total across fit window. Individual European countries
    # are excluded from the primary ranking (Europe-bloc represents them).
    totals = Counter({c: sum(cy[y] for y in range(FIT_START, FIT_END + 1))
                      for c, cy in country_year.items()
                      if c not in EUROPE})
    top_countries = [c for c, _ in totals.most_common(args.top)]

    fit_years = list(range(FIT_START, FIT_END + 1))
    proj_years = list(range(FIT_START, PROJECT_TO + 1))

    rows = []
    exp_fits = {}
    share_fits = {}

    for c in top_countries:
        counts = [country_year[c].get(y, 0) for y in fit_years]
        shares = [100 * country_year[c].get(y, 0) / max(total_by_year.get(y, 0), 1)
                  for y in fit_years]
        e = fit_exponential(fit_years, counts)
        s = fit_linear(fit_years, shares)
        exp_fits[c] = e
        share_fits[c] = s

        proj_counts_2028 = exp_model(2028 - FIT_START, e["a"], e["b"]) if e else float("nan")
        proj_counts_2030 = exp_model(2030 - FIT_START, e["a"], e["b"]) if e else float("nan")
        proj_share_2028 = s["slope"] * 2028 + s["intercept"] if s else float("nan")
        proj_share_2030 = s["slope"] * 2030 + s["intercept"] if s else float("nan")
        avg_share = sum(shares) / len(shares)

        # Phase-shift comparison: 2015–2020 vs 2021–2025
        p1_count = sum(country_year[c].get(y, 0) for y in P1_RANGE)
        p2_count = sum(country_year[c].get(y, 0) for y in P2_RANGE)
        p1_total = sum(total_by_year.get(y, 0) for y in P1_RANGE)
        p2_total = sum(total_by_year.get(y, 0) for y in P2_RANGE)
        p1_share = 100 * p1_count / p1_total if p1_total else 0
        p2_share = 100 * p2_count / p2_total if p2_total else 0
        # Per-year rate (normalizes for the 6-vs-5 year asymmetry)
        p1_rate = p1_count / len(P1_RANGE)
        p2_rate = p2_count / len(P2_RANGE)
        rate_ratio = p2_rate / p1_rate if p1_rate > 0 else float("inf")

        rows.append({
            "country": c,
            "total_2015_2025": sum(counts),
            "avg_share_pct": round(avg_share, 1),
            "p1_count_2015_2020": p1_count,
            "p2_count_2021_2025": p2_count,
            "p1_share_pct": round(p1_share, 1),
            "p2_share_pct": round(p2_share, 1),
            "share_delta_pp": round(p2_share - p1_share, 1),
            "p1_rate_per_yr": round(p1_rate, 2),
            "p2_rate_per_yr": round(p2_rate, 2),
            "rate_ratio_p2_over_p1": round(rate_ratio, 2) if rate_ratio != float("inf") else "∞",
            "cagr_pct": round(100 * e["cagr"], 1) if e else None,
            "exp_r2": round(e["r2"], 2) if e else None,
            "share_slope_pp_per_yr": round(s["slope"], 2) if s else None,
            "share_r2": round(s["r2"], 2) if s else None,
            "proj_count_2028": round(proj_counts_2028, 1),
            "proj_count_2030": round(proj_counts_2030, 1),
            "proj_share_2028_pct": round(proj_share_2028, 1),
            "proj_share_2030_pct": round(proj_share_2030, 1),
        })

    # ── CSV ────────────────────────────────────────────────────────────────
    csv_path = outdir / "geo_forecast.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {csv_path}")

    # ── Markdown summary ──────────────────────────────────────────────────
    md_lines = [
        f"# AI-for-Chips — Country leadership & forecast (N={sum(total_by_year.values())})",
        "",
        f"Fit window: {FIT_START}–{FIT_END} (2026 excluded as partial). "
        f"Projections extend to {PROJECT_TO}. Counting rule: any-affiliation "
        "(papers count once per unique country in their affiliation list).",
        "",
        "## Per-country table (top {})".format(args.top),
        "",
        "| Country | Total 2015–2025 | Avg share | CAGR (counts) | Exp R² | Share trend (pp/yr) | Share R² | Proj. count 2028 | Proj. count 2030 | Proj. share 2028 | Proj. share 2030 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['country']} | {r['total_2015_2025']} | {r['avg_share_pct']}% | "
            f"{r['cagr_pct']}% | {r['exp_r2']} | {r['share_slope_pp_per_yr']:+} | "
            f"{r['share_r2']} | {r['proj_count_2028']} | {r['proj_count_2030']} | "
            f"{r['proj_share_2028_pct']}% | {r['proj_share_2030_pct']}% |"
        )
    # Phase-shift table: 2015–2020 vs 2021–2025
    md_lines += [
        "",
        "## Phase comparison: 2015–2020 vs 2021–2025",
        "",
        f"Period 1 (P1): 2015–2020, 6 years; Period 2 (P2): 2021–2025, 5 years. "
        "*Rate* is papers per year, normalizing for the 6-vs-5 year asymmetry. "
        "*Share Δ* is the change in each country's share of global annual output between the two periods.",
        "",
        "| Country / bloc | P1 count | P2 count | P1 rate | P2 rate | Rate × | P1 share | P2 share | Share Δ |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['country']} | {r['p1_count_2015_2020']} | {r['p2_count_2021_2025']} "
            f"| {r['p1_rate_per_yr']} | {r['p2_rate_per_yr']} "
            f"| {r['rate_ratio_p2_over_p1']} "
            f"| {r['p1_share_pct']}% | {r['p2_share_pct']}% | {r['share_delta_pp']:+} pp |"
        )
    # Corpus totals for reference
    p1_total_all = sum(total_by_year.get(y, 0) for y in P1_RANGE)
    p2_total_all = sum(total_by_year.get(y, 0) for y in P2_RANGE)
    md_lines.append(
        f"| **Corpus (AI-for-Chips)** | **{p1_total_all}** | **{p2_total_all}** "
        f"| **{p1_total_all/len(P1_RANGE):.2f}** | **{p2_total_all/len(P2_RANGE):.2f}** "
        f"| **{p2_total_all/p1_total_all * len(P1_RANGE)/len(P2_RANGE):.2f}** "
        f"| 100% | 100% | 0 pp |"
    )

    # European drill-down (which European countries contribute within the bloc)
    eu_members_sorted = europe_members.most_common()
    md_lines += [
        "",
        "## European drill-down",
        "",
        f"The Europe bloc aggregates {len(eu_members_sorted)} countries "
        f"({sum(europe_members.values())} country-level contributions across "
        f"{sum(1 for c, _ in eu_members_sorted)} distinct countries, 2015–2026). "
        "Individual contributions:",
        "",
        "| Country | Papers |",
        "|---|---|",
    ]
    for country, count in eu_members_sorted:
        md_lines.append(f"| {country} | {count} |")
    md_lines += [
        "",
        "**Reading the columns:**",
        "- *CAGR (counts)* — compound annual growth rate from the exponential fit on yearly paper counts.",
        "- *Exp R²* — fit quality for the count model (1.0 = perfect, < 0.5 = poor fit, treat CAGR as indicative only).",
        "- *Share trend* — linear slope on the country's yearly share (percentage points per year).",
        "- *Share R²* — fit quality for the share trajectory.",
        "- *Projected 2028 / 2030* — extrapolated yearly count and share if the current trend continues. These are model extrapolations, not forecasts — they assume the structure that produced 2015–2025 is unchanged.",
        "",
        "## Caveats",
        "- Small-N noise: countries below ~30 total papers produce loose fits. Treat CAGR for Korea / small-contributor countries as directional only.",
        "- The share projection can exceed 100% or go negative if extrapolated far enough; bound your interpretation to the next 3–5 years.",
        "- No policy / funding shocks are modeled. The US CHIPS Act, EU Chips Act, and China's response post-date most of the fit window; their full effect may not yet be visible.",
        "",
    ]
    md_path = outdir / "geo_forecast.md"
    md_path.write_text("\n".join(md_lines))
    print(f"Wrote {md_path}")

    # ── Figures ───────────────────────────────────────────────────────────
    apply_style()
    fig_dir = outdir / "figures"
    fig_dir.mkdir(exist_ok=True)
    plot_style.set_data_dir(str(outdir))

    # Figure 1: absolute counts with exponential fits + projection
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(SINGLE_COL * 1.5, 3.2))
    for i, c in enumerate(top_countries):
        obs_years = fit_years + [2026]  # show 2026 as light marker
        obs_counts = [country_year[c].get(y, 0) for y in obs_years]
        color = COLORS[i % len(COLORS)]
        # Observed (2015-2025 solid, 2026 hollow marker to flag partial)
        ax.plot(fit_years, obs_counts[:-1], "o-", color=color, ms=3.5,
                lw=1.4, label=c, zorder=3)
        ax.plot([2026], [obs_counts[-1]], "o", color=color, ms=3.5,
                mfc="white", zorder=3)
        # Fit + projection
        e = exp_fits[c]
        if e is not None:
            proj_t = np.arange(FIT_START, PROJECT_TO + 1) - FIT_START
            proj = exp_model(proj_t, e["a"], e["b"])
            ax.plot(proj_years, proj, "--", color=color, lw=0.9, alpha=0.6,
                    zorder=2)
    ax.axvline(2025.5, color="grey", lw=0.6, ls=":", alpha=0.6)
    ax.annotate("projected", xy=(2027.5, ax.get_ylim()[1] * 0.05),
                fontsize=6, color="grey", ha="center", style="italic")
    ax.set_xlabel("Year")
    ax.set_ylabel("AI-for-Chips papers per year")
    ax.set_title("Top-{} contributing countries — exponential fits".format(args.top))
    ax.legend(fontsize=7, loc="upper left")
    ax.set_xlim(FIT_START - 0.5, PROJECT_TO + 0.5)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_geo_forecast_counts")

    # Figure 3: Share-delta (P2 − P1) — diverging horizontal bar chart
    # Sorted from biggest gainer to biggest loser. Zero line marked.
    fig, ax = plt.subplots(figsize=(SINGLE_COL * 1.5, 2.8))
    deltas = [(r["country"], r["share_delta_pp"]) for r in rows]
    deltas.sort(key=lambda x: x[1], reverse=True)
    names = [d[0] for d in deltas]
    values = [d[1] for d in deltas]
    colors_bar = [COLORS[2] if v > 0 else COLORS[1] for v in values]  # green pos / red neg
    y_positions = np.arange(len(names))
    ax.barh(y_positions, values, color=colors_bar, height=0.6, edgecolor="none")
    ax.axvline(0, color="#333", lw=0.8, zorder=2)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()  # biggest gainer at top
    ax.set_xlabel("Change in share of AI-for-Chips output (percentage points)")
    ax.set_title(f"Share shift: P1 (2015–2020) → P2 (2021–2025)")
    for y_i, v in zip(y_positions, values):
        offset = 0.4 if v >= 0 else -0.4
        ha = "left" if v >= 0 else "right"
        ax.text(v + offset, y_i, f"{v:+.1f} pp", va="center", ha=ha, fontsize=7)
    format_axes(ax)
    xmax = max(abs(v) for v in values) * 1.25
    ax.set_xlim(-xmax, xmax)
    fig.tight_layout()
    save_figure(fig, "fig_geo_share_delta")

    # Figure 2: share trajectory with linear fits + projection
    fig, ax = plt.subplots(figsize=(SINGLE_COL * 1.5, 3.2))
    for i, c in enumerate(top_countries):
        obs_years = fit_years + [2026]
        obs_shares = [100 * country_year[c].get(y, 0) / max(total_by_year.get(y, 0), 1)
                      for y in obs_years]
        color = COLORS[i % len(COLORS)]
        ax.plot(fit_years, obs_shares[:-1], "o-", color=color, ms=3.5,
                lw=1.4, label=c, zorder=3)
        ax.plot([2026], [obs_shares[-1]], "o", color=color, ms=3.5,
                mfc="white", zorder=3)
        s = share_fits[c]
        if s is not None:
            proj_vals = [s["slope"] * y + s["intercept"] for y in proj_years]
            ax.plot(proj_years, proj_vals, "--", color=color, lw=0.9,
                    alpha=0.6, zorder=2)
    ax.axvline(2025.5, color="grey", lw=0.6, ls=":", alpha=0.6)
    ax.set_xlabel("Year")
    ax.set_ylabel("Share of AI-for-Chips papers (%)")
    ax.set_title("Top-{} contributing countries — share trajectory".format(args.top))
    ax.legend(fontsize=7, loc="upper left")
    ax.set_xlim(FIT_START - 0.5, PROJECT_TO + 0.5)
    ax.set_ylim(bottom=0)
    format_axes(ax)
    fig.tight_layout()
    save_figure(fig, "fig_geo_forecast_share")


if __name__ == "__main__":
    main()
