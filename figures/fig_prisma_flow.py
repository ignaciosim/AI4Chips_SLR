#!/usr/bin/env python3
"""PRISMA 2020 flow diagram for the AI-for-Chips SLR.

Produces a publication-quality PRISMA flow diagram showing the funnel from
6,835 Scopus records retrieved through to 53 shortlist entries displayed in
the paper. All counts come from the live pipeline state (scopus_out10/).

Output:
    scopus_out10/figures/fig_prisma_flow.{pdf,png}
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import plot_style
from plot_style import apply_style, save_figure, DOUBLE_COL

# ── Pipeline counts (reflect scopus_out10 state, 2015–2026 window) ────────
SCOPUS_RECORDS   = 6835   # across 6 phase queries
DUPLICATES       = 1304
AFTER_DEDUP      = 5531
NON_AI4CHIPS     = 3096   # unclassified + chips-for-AI + ambiguous
CLASSIFIED_AI    = 2435   # ai_for_chips at any confidence
LOW_MED_CONF     = 2099
HIGH_CONF_RAW    = 336    # high-confidence ai_for_chips before GaN filter
GAN_FP_REMOVED   = 15
AFTER_GAN        = 321    # high-confidence corpus on disk
SURVEYS_REMOVED  = 4
MANUAL_FP        = 19     # chips-for-AI / off-topic / algorithmic-not-ML
FINAL_CORPUS     = 298    # analysed pool post-curation
SHORTLIST_ROWS   = 53     # anchors + exemplars + recent + newest + curator


# ── Colour palette (publication-neutral greys + one accent) ──────────────
MAIN_FILL   = "#f0f0f4"
MAIN_EDGE   = "#333333"
EXCL_FILL   = "#fff4e6"
EXCL_EDGE   = "#a65a00"
INCL_FILL   = "#e0efff"
INCL_EDGE   = "#0072B2"
SECTION_FILL = "#333333"


def draw_box(ax, x, y, w, h, text, fill, edge, font_weight="normal",
             font_color="#000", font_size=7.5):
    """Draw a rounded rectangle box with centered multi-line text."""
    box = FancyBboxPatch((x, y), w, h,
                        boxstyle="round,pad=0.02,rounding_size=0.06",
                        fc=fill, ec=edge, lw=0.8, zorder=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=font_size, color=font_color, weight=font_weight,
            zorder=3)


def draw_arrow(ax, x1, y1, x2, y2, **kw):
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           arrowstyle="-|>", mutation_scale=12,
                           color="#333", lw=0.8, zorder=1, **kw)
    ax.add_patch(arrow)


def main():
    apply_style()
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 8.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis("off")

    # Geometry
    main_x, main_w = 1.5, 4.5
    excl_x, excl_w = 6.8, 2.8
    box_h = 1.0
    y_top = 13

    # ── Section label: IDENTIFICATION ────────────────────────────────────
    ax.text(0.3, y_top + 0.2, "Identification", rotation=90,
            ha="center", va="center", fontsize=9, weight="bold",
            color=SECTION_FILL)
    # Box: Records identified
    y = y_top - box_h
    draw_box(ax, main_x, y, main_w, box_h,
             f"Records identified from Scopus\n(6 lifecycle-phase queries)\n"
             f"n = {SCOPUS_RECORDS:,}",
             MAIN_FILL, MAIN_EDGE, font_weight="bold")

    # ── Section label: SCREENING ─────────────────────────────────────────
    y_dedup = y - 1.4
    ax.text(0.3, y_dedup + 0.3, "Screening", rotation=90,
            ha="center", va="center", fontsize=9, weight="bold",
            color=SECTION_FILL)
    draw_arrow(ax, main_x + main_w / 2, y, main_x + main_w / 2, y_dedup + box_h)
    # Box: After dedup
    draw_box(ax, main_x, y_dedup, main_w, box_h,
             f"Records after de-duplication\nn = {AFTER_DEDUP:,}",
             MAIN_FILL, MAIN_EDGE)
    # Exclusion: duplicates
    draw_box(ax, excl_x, y_dedup + 0.15, excl_w, box_h - 0.3,
             f"Duplicates removed\nn = {DUPLICATES:,}",
             EXCL_FILL, EXCL_EDGE)
    draw_arrow(ax, main_x + main_w, y_dedup + box_h / 2,
               excl_x, y_dedup + box_h / 2)

    # Box: Screened by classifier
    y_screen = y_dedup - 1.4
    draw_arrow(ax, main_x + main_w / 2, y_dedup,
               main_x + main_w / 2, y_screen + box_h)
    draw_box(ax, main_x, y_screen, main_w, box_h,
             f"Records screened\n(ontology-based classifier,\ntitle + abstract)\n"
             f"n = {AFTER_DEDUP:,}",
             MAIN_FILL, MAIN_EDGE)
    # Exclusion: non-AI-for-Chips
    draw_box(ax, excl_x, y_screen + 0.15, excl_w, box_h - 0.3,
             f"Excluded — not AI-for-Chips\n"
             f"(unclassified, chips-for-AI,\nambiguous)\nn = {NON_AI4CHIPS:,}",
             EXCL_FILL, EXCL_EDGE)
    draw_arrow(ax, main_x + main_w, y_screen + box_h / 2,
               excl_x, y_screen + box_h / 2)

    # ── Section label: ELIGIBILITY ───────────────────────────────────────
    y_elig = y_screen - 1.4
    ax.text(0.3, y_elig + 0.3, "Eligibility", rotation=90,
            ha="center", va="center", fontsize=9, weight="bold",
            color=SECTION_FILL)
    draw_arrow(ax, main_x + main_w / 2, y_screen,
               main_x + main_w / 2, y_elig + box_h)
    # Box: classified as AI-for-Chips
    draw_box(ax, main_x, y_elig, main_w, box_h,
             f"Classified as AI-for-Chips\n(any confidence)\nn = {CLASSIFIED_AI:,}",
             MAIN_FILL, MAIN_EDGE)
    # Exclusion: low/medium confidence
    draw_box(ax, excl_x, y_elig + 0.15, excl_w, box_h - 0.3,
             f"Excluded — low/medium\nconfidence\nn = {LOW_MED_CONF:,}",
             EXCL_FILL, EXCL_EDGE)
    draw_arrow(ax, main_x + main_w, y_elig + box_h / 2,
               excl_x, y_elig + box_h / 2)

    # Box: high-confidence raw
    y_hc = y_elig - 1.4
    draw_arrow(ax, main_x + main_w / 2, y_elig,
               main_x + main_w / 2, y_hc + box_h)
    draw_box(ax, main_x, y_hc, main_w, box_h,
             f"High-confidence AI-for-Chips\n(raw)\nn = {HIGH_CONF_RAW:,}",
             MAIN_FILL, MAIN_EDGE)
    # Exclusion: GaN false positives
    draw_box(ax, excl_x, y_hc + 0.15, excl_w, box_h - 0.3,
             f"Excluded — GaN material\nfalse positives\nn = {GAN_FP_REMOVED}",
             EXCL_FILL, EXCL_EDGE)
    draw_arrow(ax, main_x + main_w, y_hc + box_h / 2,
               excl_x, y_hc + box_h / 2)

    # Box: after GaN filter
    y_gan = y_hc - 1.4
    draw_arrow(ax, main_x + main_w / 2, y_hc,
               main_x + main_w / 2, y_gan + box_h)
    draw_box(ax, main_x, y_gan, main_w, box_h,
             f"High-confidence corpus\n(after GaN correction)\nn = {AFTER_GAN}",
             MAIN_FILL, MAIN_EDGE)
    # Exclusion: manual curation (combined)
    draw_box(ax, excl_x, y_gan + 0.15, excl_w, box_h - 0.3,
             f"Excluded by manual curation:\n"
             f"surveys n = {SURVEYS_REMOVED}; manual\n"
             f"false positives n = {MANUAL_FP}\n"
             f"(total n = {SURVEYS_REMOVED + MANUAL_FP})",
             EXCL_FILL, EXCL_EDGE)
    draw_arrow(ax, main_x + main_w, y_gan + box_h / 2,
               excl_x, y_gan + box_h / 2)

    # ── Section label: INCLUDED ──────────────────────────────────────────
    y_final = y_gan - 1.4
    ax.text(0.3, y_final + 0.3, "Included", rotation=90,
            ha="center", va="center", fontsize=9, weight="bold",
            color=SECTION_FILL)
    draw_arrow(ax, main_x + main_w / 2, y_gan,
               main_x + main_w / 2, y_final + box_h)
    draw_box(ax, main_x, y_final, main_w, box_h,
             f"Included for synthesis\n(full analysed corpus)\nn = {FINAL_CORPUS}",
             INCL_FILL, INCL_EDGE, font_weight="bold")

    # Final: shortlist displayed in paper
    y_sl = y_final - 1.25
    draw_arrow(ax, main_x + main_w / 2, y_final,
               main_x + main_w / 2, y_sl + box_h - 0.1)
    draw_box(ax, main_x, y_sl, main_w, box_h - 0.1,
             f"Shortlist displayed in paper\n"
             f"(anchors + exemplars + recent\n+ newest + curator)\nn = {SHORTLIST_ROWS}",
             INCL_FILL, INCL_EDGE, font_weight="bold")

    fig.suptitle(
        "PRISMA 2020 Flow Diagram — AI-for-Chips SLR",
        fontsize=11, y=0.98, weight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save_figure(fig, "fig_prisma_flow")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out10")
    args = ap.parse_args()
    plot_style.set_data_dir(str(Path(__file__).resolve().parent.parent / args.datadir))
    main()
