"""Master script to generate all publication-quality figures.

Usage:
    python3 generate_all_figures.py             # generate all figures
    python3 generate_all_figures.py --only pub_volume  # single figure
"""

import argparse
import importlib
import os
import sys
import time

# Add parent directory to path so fig_*.py modules can find plot_style
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# Add own directory so importlib.import_module can find fig_* modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FIGURE_MODULES = [
    ("fig_pub_volume",       "fig_pub_volume.pdf"),
    ("fig_ai_methods",       "fig_ai_methods_totals.pdf, fig_ai_methods_trends.pdf"),
    ("fig_chip_tasks",       "fig_chip_tasks_totals.pdf, fig_chip_tasks_trends.pdf"),
    ("fig_analog_digital",   "fig_analog_digital_donut.pdf, fig_analog_digital_trends.pdf"),
    ("fig_commercial_apps",  "fig_commercial_apps_totals.pdf, fig_commercial_apps_trends.pdf"),
    ("fig_venues",           "fig_venues_totals.pdf, fig_venues_trends.pdf"),
    ("fig_geo",              "fig_geo_totals.pdf, fig_geo_trends.pdf, fig_geo_periods.pdf"),
    ("fig_geo_all",          "fig_geo_all_totals.pdf, fig_geo_all_trends.pdf, fig_geo_all_regions.pdf"),
    ("fig_geo_contrast",     "fig_geo_share_contrast.pdf, fig_geo_specialization.pdf, fig_geo_trends_contrast.pdf, fig_geo_trends_overlay.pdf, fig_geo_trends_overlay_counts.pdf, fig_geo_trends_facets.pdf"),
    ("fig_citation_impact",  "fig_citation_boxplot.pdf, fig_citation_methods.pdf, fig_citation_tasks.pdf"),
    ("fig_citation_venues",  "fig_citation_venues.pdf"),
    ("fig_method_country",   "fig_method_country_heatmap.pdf"),
    ("fig_country_profile",  "fig_country_profile.pdf"),
    ("fig_soft_ald",         "fig_emerging_topics.pdf"),
    ("fig_task_combinations","fig_task_combinations.pdf"),
    ("fig_cross_stage",      "fig_cross_stage.pdf"),
    ("fig_method_stage",     "fig_method_stage.pdf"),
    ("fig_method_evolution", "fig_method_evolution.pdf"),
    ("fig_method_stage_time","fig_method_stage_time.pdf"),
    ("fig_keyword_country",  "fig_keyword_country.pdf"),
    ("fig_method_task",      "fig_method_task_heatmap.pdf"),
    ("fig_growth_model",     "fig_growth_model.pdf"),
    ("fig_growth_contrast",  "fig_growth_contrast.pdf"),
    ("fig_citation_analysis","fig_cite_year_box.pdf, fig_cite_concentration.pdf, fig_cite_methods.pdf, fig_cite_tasks.pdf, fig_cite_venues.pdf"),
]


def main():
    parser = argparse.ArgumentParser(description="Generate all SLR figures")
    parser.add_argument("--only", type=str, default=None,
                        help="Generate only this figure (module name without .py)")
    parser.add_argument("--datadir", default=None,
                        help="Path to data directory (default: scopus_out7)")
    args = parser.parse_args()

    if args.datadir:
        import plot_style
        plot_style.set_data_dir(args.datadir)

    if args.only:
        # Match partial names
        matches = [(m, pdf) for m, pdf in FIGURE_MODULES
                    if args.only in m]
        if not matches:
            print(f"No figure module matching '{args.only}'")
            print("Available:", ", ".join(m for m, _ in FIGURE_MODULES))
            sys.exit(1)
        targets = matches
    else:
        targets = FIGURE_MODULES

    total = len(targets)
    success = 0
    t0 = time.time()

    for i, (module_name, pdf_name) in enumerate(targets, 1):
        print(f"\n[{i}/{total}] Generating {pdf_name} ...")
        try:
            mod = importlib.import_module(module_name)
            mod.main()
            success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"Done: {success}/{total} figures generated in {elapsed:.1f}s")
    if success < total:
        print(f"  {total - success} figure(s) FAILED")
    import plot_style
    print(f"Output: {plot_style.FIG_DIR}")

    # Report the manuscript set explicitly. A figure that silently stops being
    # produced is easy to miss when it is one PNG among forty-odd; when it is
    # one of the ten the paper actually prints, it should be loud.
    man_dir = os.path.join(plot_style.FIG_DIR, plot_style.MANUSCRIPT_SUBDIR)
    missing = [n for n in plot_style.MANUSCRIPT_FIGURES
               if not any(os.path.exists(os.path.join(man_dir, f"{n}.{e}"))
                          for e in plot_style.FIGURE_FORMATS)]
    print(f"  {plot_style.MANUSCRIPT_SUBDIR}/: "
          f"{len(plot_style.MANUSCRIPT_FIGURES) - len(missing)}"
          f"/{len(plot_style.MANUSCRIPT_FIGURES)} manuscript figures")
    for n in missing:
        print(f"    MISSING: {n} \u2014 {plot_style.MANUSCRIPT_FIGURES[n]}")


if __name__ == "__main__":
    main()
