# SLR pipeline — end-to-end runner.
#
# Usage:
#   make setup                        # create .venv and install pinned deps
#   make all DATADIR=scopus_out11     # run the Scopus pipeline end-to-end
#   make figures DATADIR=scopus_out11 # regenerate figures only
#   make patents DATADIR=scopus_out11 # patent-landscape companion (BigQuery)
#   make preflight                    # sanity-check credentials + deps
#   make clean                        # remove generated outputs (keep raw)
#   make nuke                         # remove EVERYTHING including raw fetch
#
# Overridable variables:
#   DATADIR       — per-run data/output directory (default: scopus_out10)
#   CONFIG        — Scopus API config JSON (default: ../config.json)
#   VENUES        — venue allow-list (default: ../venues_eda.txt)
#   START_YEAR    — retrieval window start (default: 2015)
#   END_YEAR      — retrieval window end  (default: 2026)
#   MAX_PAGES     — Scopus pagination cap (default: 80)
#   GCP_PROJECT   — GCP project for patent BigQuery (optional)

PY              ?= python3
VENV            ?= .venv
DATADIR         ?= scopus_out10
CONFIG          ?= ../config.json
VENUES          ?= ../venues_eda.txt
START_YEAR      ?= 2015
END_YEAR        ?= 2026
MAX_PAGES       ?= 80

# Stage output files (drive dependency tracking).
RAW_MERGED      := $(DATADIR)/raw_scopus_all.csv
CLASSIFIED      := $(DATADIR)/classified_scopus.csv
FINAL_JSON      := $(DATADIR)/final_ai4chips_high_only.json
SHORTLIST_STAMP := $(DATADIR)/.shortlist.stamp
FIGURES_STAMP   := $(DATADIR)/figures/.figures.stamp
PATENTS_CSV     := $(DATADIR)/patents_vs_publications_strict.csv

.PHONY: all setup preflight fetch merge classify final shortlist figures \
        analysis patents clean nuke help

help:
	@echo "SLR pipeline targets:"
	@echo "  setup       create virtualenv and install pinned deps"
	@echo "  preflight   verify credentials + environment before running"
	@echo "  all         run the Scopus pipeline end-to-end (fetch→figures)"
	@echo "  fetch       Scopus retrieval + dedup/merge"
	@echo "  classify    ontology-based classification + pivots"
	@echo "  final       high-confidence AI-for-Chips filter (post GaN FP)"
	@echo "  shortlist   curated per-stage shortlist (survey + manual FP filter)"
	@echo "  figures     (re)generate all publication figures"
	@echo "  analysis    run the text-output analysis scripts"
	@echo "  patents     patent-landscape companion (needs BigQuery auth)"
	@echo "  clean       remove generated outputs (keep raw Scopus fetch)"
	@echo "  nuke        remove EVERYTHING (including expensive raw fetch)"
	@echo ""
	@echo "Current run vars: DATADIR=$(DATADIR) YEARS=$(START_YEAR)-$(END_YEAR)"

# ── One-shot environment setup ─────────────────────────────────────────────
setup: $(VENV)/bin/python

$(VENV)/bin/python: requirements.txt
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt
	@echo ""
	@echo "Virtualenv ready at $(VENV)/. Activate with:"
	@echo "    source $(VENV)/bin/activate"

# ── Pre-flight: verify credentials and deps before burning hours on fetch ──
preflight:
	@echo "Preflight for DATADIR=$(DATADIR):"
	@test -f $(CONFIG)  || (echo "  [FAIL] missing Scopus config: $(CONFIG)"      && exit 1)
	@test -f $(VENUES)  || (echo "  [FAIL] missing venues allow-list: $(VENUES)"  && exit 1)
	@echo "  [ok]   Scopus config:      $(CONFIG)"
	@echo "  [ok]   Venues allow-list:  $(VENUES)"
	@$(PY) -c "import pandas, numpy, matplotlib, scipy, requests; print('  [ok]   Core deps importable')"
	@$(PY) -c "import google.cloud.bigquery" 2>/dev/null && \
	    echo "  [ok]   google-cloud-bigquery importable (patent target available)" || \
	    echo "  [warn] google-cloud-bigquery missing — 'make patents' will fail"
	@command -v gcloud >/dev/null 2>&1 && \
	    echo "  [ok]   gcloud CLI on PATH" || \
	    echo "  [warn] gcloud CLI missing — 'make patents' will fail"
	@echo "Preflight passed."

# ── Stage 1: Scopus fetch (expensive; hours) + merge/dedup ──────────────────
# Depends on ontology, fetch/merge code, and the venues allow-list.
# Guarded by $(RAW_MERGED) timestamp so re-running is a no-op when fresh.
$(RAW_MERGED): fetch_scopus.py merge_scopus.py slr_ontology.py $(VENUES) $(CONFIG)
	@mkdir -p $(DATADIR)
	$(PY) fetch_scopus.py \
	    --config      $(CONFIG) \
	    --outdir      $(DATADIR) \
	    --venues_file $(VENUES) \
	    --max_pages   $(MAX_PAGES) \
	    --start_year  $(START_YEAR) \
	    --end_year    $(END_YEAR)
	$(PY) merge_scopus.py $(DATADIR)/

fetch merge: $(RAW_MERGED)

# ── Stage 2: ontology-based classification + pivot tables ──────────────────
$(CLASSIFIED): $(RAW_MERGED) classify_scopus.py slr_ontology.py
	$(PY) classify_scopus.py $(RAW_MERGED)

classify: $(CLASSIFIED)

# ── Stage 3: final high-confidence filter (+ GaN false-positive removal) ───
$(FINAL_JSON): $(CLASSIFIED) create_final_high_confidence_only.py
	$(PY) create_final_high_confidence_only.py $(DATADIR)

final: $(FINAL_JSON)

# ── Stage 4: curated per-stage shortlist (applies survey + EXCLUDE_DOIS) ───
$(SHORTLIST_STAMP): $(FINAL_JSON) analysis/generate_stage_shortlist.py
	$(PY) analysis/generate_stage_shortlist.py --datadir $(DATADIR)
	@touch $(SHORTLIST_STAMP)

shortlist: $(SHORTLIST_STAMP)

# ── Stage 5: all publication figures (17-figure master runner) ─────────────
$(FIGURES_STAMP): $(FINAL_JSON) $(wildcard figures/fig_*.py) \
                  figures/generate_all_figures.py plot_style.py
	$(PY) figures/generate_all_figures.py --datadir $(DATADIR)
	@mkdir -p $(DATADIR)/figures && touch $(FIGURES_STAMP)

figures: $(FIGURES_STAMP)

# ── Stage 6: text-output analysis scripts (concise selection) ──────────────
# The 15+ analysis/ scripts are all standalone and emit text/CSV. We run a
# curated subset here; add more with `analysis: + <script>` as needed.
analysis: $(FINAL_JSON)
	$(PY) analysis/ai_method_prevalence.py    --datadir $(DATADIR)
	$(PY) analysis/chip_task.py               --datadir $(DATADIR)
	$(PY) analysis/venues_trends.py           --datadir $(DATADIR)
	$(PY) analysis/geo_analysis.py            --datadir $(DATADIR)
	$(PY) analysis/citation_impact.py         --datadir $(DATADIR)
	$(PY) analysis/commercial_application.py  --datadir $(DATADIR)

# ── Patent-landscape companion (branches off; needs GCP auth) ──────────────
# Reads $(FINAL_JSON) to compute per-company SLR pub counts against the
# curated corpus, then queries BigQuery for matching patents.
$(PATENTS_CSV): $(FINAL_JSON) analysis/patent_analysis.py
	$(PY) analysis/patent_analysis.py --datadir $(DATADIR) \
	    $(if $(GCP_PROJECT),--project $(GCP_PROJECT),)

patents: $(PATENTS_CSV)

# ── End-to-end ─────────────────────────────────────────────────────────────
# `all` runs everything except patents (which needs separate GCP auth).
all: $(FIGURES_STAMP) $(SHORTLIST_STAMP)
	@echo ""
	@echo "Pipeline complete for $(DATADIR)/."
	@echo "  Corpus:     $(FINAL_JSON)"
	@echo "  Shortlist:  $(DATADIR)/stage_shortlists.csv"
	@echo "  Figures:    $(DATADIR)/figures/"
	@echo ""
	@echo "Next steps (optional):"
	@echo "  make analysis DATADIR=$(DATADIR)   # text analyses"
	@echo "  make patents  DATADIR=$(DATADIR)   # patent-landscape (BigQuery)"

# ── Housekeeping ──────────────────────────────────────────────────────────
# `clean` preserves the expensive raw Scopus fetch; use `nuke` for full reset.
clean:
	@echo "Removing generated outputs in $(DATADIR)/ (keeping raw fetch)..."
	rm -f  $(CLASSIFIED) $(FINAL_JSON) $(DATADIR)/final_ai4chips_high_only.csv
	rm -f  $(DATADIR)/ai_methods_long.csv $(DATADIR)/pivot_*.csv
	rm -f  $(DATADIR)/classification_summary.txt
	rm -f  $(SHORTLIST_STAMP) $(FIGURES_STAMP)
	rm -rf $(DATADIR)/figures
	@echo "Raw fetch retained at $(DATADIR)/raw_scopus_*.jsonl"

nuke:
	@echo "Removing EVERYTHING in $(DATADIR)/ including raw fetch..."
	rm -rf $(DATADIR)

# Debug helper: `make -n all` dry-runs the whole chain so you can see what
# would be executed without actually launching anything.
