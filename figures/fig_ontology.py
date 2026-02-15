"""Ontology class diagram for the Silicon Lifecycle SLR.

Visualises the five top-level categories from slr_ontology.py, their
subclasses, and the two directional relationships (AI-for-Chips,
Chips-for-AI) as a publication-quality matplotlib figure.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Reuse project style
from plot_style import apply_style, save_figure, COLORS, DOUBLE_COL

apply_style()

# ── Ontology data (mirrors slr_ontology.py) ──────────────────────────────

PHASES = ["Design", "Fabrication", "Packaging\n& Assembly", "In-Field\nOperation"]

AI_METHODS = [
    "Deep Learning", "Graph Neural Nets", "Reinforcement Learning",
    "LLM / Foundation", "Bayesian / Probabilistic",
    "Evolutionary / Metaheur.", "Classical ML", "Symbolic Reasoning",
    "Transfer Learning", "Anomaly Detection", "GANs", "General ML Signals",
]

CHIP_TASKS = [
    "Placement", "Routing", "Timing Analysis", "Logic Synthesis",
    "Power Analysis", "Design Space Expl.", "Analog Circuit Design",
    "Verification", "Calibration", "Lithography Optim.",
    "Hotspot Detection", "Defect Detection", "Yield Prediction",
    "Wafer Map Analysis", "Process Optimization", "Test Generation",
    "Fault Diagnosis", "Reliability Analysis", "Thermal Management",
    "Security Analysis",
]

HW_ARTIFACTS = [
    "Neural Accelerator", "In-Memory Computing",
    "Neuromorphic Chip", "FPGA Accelerator",
    "Specialized Arch.",
]

AI_WORKLOADS = [
    "DNN Inference", "DNN Training",
    "Transformer Inference", "Spiking NN Execution",
    "Generic AI Workload",
]


# ── Drawing helpers ──────────────────────────────────────────────────────

def draw_box(ax, x, y, w, h, title, items, color, fontsize=6.5,
             title_fontsize=8, max_items=None):
    """Draw a rounded box with a title bar and listed items."""
    # Main box
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02",
        facecolor="white", edgecolor=color, linewidth=1.2,
    )
    ax.add_patch(box)

    # Title bar
    title_h = 0.045
    title_bar = FancyBboxPatch(
        (x, y + h - title_h), w, title_h,
        boxstyle="round,pad=0.02",
        facecolor=color, edgecolor=color, linewidth=1.2,
    )
    ax.add_patch(title_bar)
    # Clip bottom corners of title bar with a white rectangle
    clip_rect = mpatches.Rectangle(
        (x, y + h - title_h), w, title_h * 0.5,
        facecolor=color, edgecolor="none",
    )
    ax.add_patch(clip_rect)

    ax.text(x + w / 2, y + h - title_h / 2, title,
            ha="center", va="center", fontsize=title_fontsize,
            fontweight="bold", color="white")

    # Items
    display = items if max_items is None else items[:max_items]
    n_display = len(display)
    item_area_top = y + h - title_h - 0.012
    line_h = min(0.028, (item_area_top - y - 0.01) / max(n_display, 1))

    for i, item in enumerate(display):
        iy = item_area_top - i * line_h
        ax.text(x + 0.015, iy, f"\u2022 {item}",
                ha="left", va="top", fontsize=fontsize, color="#333333")

    if max_items is not None and len(items) > max_items:
        iy = item_area_top - n_display * line_h
        remaining = len(items) - max_items
        ax.text(x + 0.015, iy, f"  + {remaining} more",
                ha="left", va="top", fontsize=fontsize,
                color="#888888", fontstyle="italic")


def draw_arrow(ax, x1, y1, x2, y2, label, color="#444444"):
    """Draw a labeled arrow between two points."""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="->,head_width=4,head_length=3",
        connectionstyle="arc3,rad=0",
        color=color, linewidth=1.5, zorder=5,
    )
    ax.add_patch(arrow)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ax.text(mx, my + 0.018, label, ha="center", va="bottom",
            fontsize=7, fontstyle="italic", color=color)


def draw_phase_pipeline(ax, y_center, x_start, x_end):
    """Draw the lifecycle phases as a horizontal pipeline with arrows."""
    n = len(PHASES)
    total_w = x_end - x_start
    box_w = total_w * 0.20
    gap = (total_w - n * box_w) / (n - 1) if n > 1 else 0
    phase_color = COLORS[5]  # sky blue

    for i, phase in enumerate(PHASES):
        bx = x_start + i * (box_w + gap)
        by = y_center - 0.03
        bh = 0.06
        box = FancyBboxPatch(
            (bx, by), box_w, bh,
            boxstyle="round,pad=0.01",
            facecolor=phase_color, edgecolor="#0072B2",
            linewidth=1.0, alpha=0.85,
        )
        ax.add_patch(box)
        ax.text(bx + box_w / 2, y_center, phase,
                ha="center", va="center", fontsize=7,
                fontweight="bold", color="white")

        # Arrow to next phase
        if i < n - 1:
            ax.annotate(
                "", xy=(bx + box_w + gap * 0.15, y_center),
                xytext=(bx + box_w + 0.005, y_center),
                arrowprops=dict(arrowstyle="->", color="#0072B2",
                                lw=1.2),
            )


def main():
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Title ─────────────────────────────────────────────────────────
    ax.text(0.5, 0.97, "Silicon Lifecycle SLR Ontology",
            ha="center", va="top", fontsize=11, fontweight="bold")
    ax.text(0.5, 0.935,
            "5 top-level classes  \u00b7  44 subclasses  \u00b7  233 surface forms",
            ha="center", va="top", fontsize=8, color="#666666")

    # ── Lifecycle phases (top row) ────────────────────────────────────
    ax.text(0.5, 0.895, "Lifecycle Phases", ha="center", va="top",
            fontsize=8.5, fontweight="bold", color="#0072B2")
    draw_phase_pipeline(ax, y_center=0.845, x_start=0.08, x_end=0.92)

    # ── Directional labels ────────────────────────────────────────────
    # Left half: AI for Chips
    ax.text(0.25, 0.785, "AI for Chips", ha="center", va="top",
            fontsize=9, fontweight="bold", color=COLORS[0],
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#E8F4FD",
                      edgecolor=COLORS[0], linewidth=0.8))

    # Right half: Chips for AI
    ax.text(0.75, 0.785, "Chips for AI", ha="center", va="top",
            fontsize=9, fontweight="bold", color=COLORS[1],
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#FDE8E0",
                      edgecolor=COLORS[1], linewidth=0.8))

    # ── AI Methods box (left-left) ────────────────────────────────────
    am_x, am_y, am_w, am_h = 0.02, 0.04, 0.22, 0.70
    draw_box(ax, am_x, am_y, am_w, am_h,
             f"AI Methods ({len(AI_METHODS)})", AI_METHODS,
             color=COLORS[0], fontsize=6.0)

    # ── Chip Design Tasks box (left-right) ────────────────────────────
    ct_x, ct_y, ct_w, ct_h = 0.28, 0.04, 0.22, 0.70
    draw_box(ax, ct_x, ct_y, ct_w, ct_h,
             f"Chip Design Tasks ({len(CHIP_TASKS)})", CHIP_TASKS,
             color=COLORS[2], fontsize=5.5)

    # Arrow: AI Methods → Chip Design Tasks
    draw_arrow(ax, am_x + am_w + 0.005, am_y + am_h / 2,
               ct_x - 0.005, ct_y + ct_h / 2,
               "appliedTo", color=COLORS[0])

    # ── HW Artifacts box (right-left) ─────────────────────────────────
    hw_x, hw_y, hw_w, hw_h = 0.54, 0.24, 0.20, 0.50
    draw_box(ax, hw_x, hw_y, hw_w, hw_h,
             f"HW Artifacts ({len(HW_ARTIFACTS)})", HW_ARTIFACTS,
             color=COLORS[1], fontsize=6.0)

    # ── AI Workloads box (right-right) ────────────────────────────────
    wl_x, wl_y, wl_w, wl_h = 0.78, 0.24, 0.20, 0.50
    draw_box(ax, wl_x, wl_y, wl_w, wl_h,
             f"AI Workloads ({len(AI_WORKLOADS)})", AI_WORKLOADS,
             color=COLORS[3], fontsize=6.0)

    # Arrow: HW Artifacts → AI Workloads
    draw_arrow(ax, hw_x + hw_w + 0.005, hw_y + hw_h / 2,
               wl_x - 0.005, wl_y + wl_h / 2,
               "optimizedFor", color=COLORS[1])

    # ── Supporting elements (bottom-right) ────────────────────────────
    supp_x, supp_y = 0.55, 0.04
    ax.text(supp_x, supp_y + 0.17, "Supporting Vocabularies",
            ha="left", va="top", fontsize=7.5, fontweight="bold",
            color="#555555")
    supports = [
        ("Chip Anchor", "Domain filter (IC/EDA relevance)"),
        ("AI Umbrella", "Broad AI terms for focus filtering"),
        ("Heuristic Phrases", "Fallback chips-for-AI signals"),
    ]
    for i, (name, desc) in enumerate(supports):
        iy = supp_y + 0.12 - i * 0.04
        ax.text(supp_x + 0.01, iy, f"\u25B8 {name}", ha="left", va="top",
                fontsize=6.5, fontweight="bold", color="#555555")
        ax.text(supp_x + 0.155, iy, desc, ha="left", va="top",
                fontsize=6.0, color="#888888")

    # ── Dashed separator between the two halves ──────────────────────
    ax.plot([0.50, 0.50], [0.02, 0.76], ls=":", color="#CCCCCC",
            linewidth=0.8, zorder=0)

    save_figure(fig, "fig_ontology")
    plt.close(fig)
    print("Saved fig_ontology (.pdf + .png)")


if __name__ == "__main__":
    main()
