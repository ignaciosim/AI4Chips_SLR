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
    ("fig_geo_all",          "fig_geo_all_totals.pdf, fig_geo_all_regions.pdf"),
    ("fig_citation_impact",  "fig_citation_boxplot.pdf, fig_citation_methods.pdf, fig_citation_tasks.pdf"),
    ("fig_citation_venues",  "fig_citation_venues.pdf"),
    ("fig_method_country",   "fig_method_country_heatmap.pdf"),
    ("fig_soft_ald",         "fig_emerging_topics.pdf"),
    ("fig_task_combinations","fig_task_combinations.pdf"),
    ("fig_keyword_country",  "fig_keyword_country.pdf"),
    ("fig_method_task",      "fig_method_task_heatmap.pdf"),
    ("fig_growth_model",     "fig_growth_model.pdf"),
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


if __name__ == "__main__":
    main()
