# AI4Chips SLR Pipeline

Systematic Literature Review pipeline for AI applications in chip design
(the AI-for-Chips lifecycle: design, fabrication, packaging, transit,
in-field, disposal). All domain vocabulary is defined **once** in
`slr_ontology.py` and consumed by every downstream script.

## Architecture

```
slr_ontology.py              ← single source of truth (vocabulary, taxonomy, query builders)
plot_style.py                ← shared plotting rcParams, palette, and data loaders
    │                          (imported by every script in figures/ and analysis/)
    │
    ├── fetch_scopus.py                      ← step 1: Scopus API retrieval
    │       │
    │       ▼
    │   raw_scopus_<phase>.jsonl + .csv      (design, fabrication, packaging, transit,
    │       │                                 in_field, disposal)
    │       │
    │   merge_scopus.py                      ← step 2: deduplicate + flatten
    │       │
    │       ▼
    │   raw_scopus_all.{csv,jsonl}
    │       │
    │   classify_scopus.py                   ← step 3: entity extraction + directionality
    │       │                                   + method tagging + pivot tables
    │       ▼
    │   classified_scopus.csv  +  ai_methods_long.csv  +  pivot_*.csv
    │       │
    │   create_final_high_confidence_only.py ← step 4: high-confidence AI-for-Chips
    │       │                                   filter + GaN-material FP removal
    │       ▼
    │   final_ai4chips_high_only.{csv,json}  (high-confidence AI-for-Chips corpus)
    │       │
    │       ├── analysis/generate_stage_shortlist.py    ← step 5a: survey + manual-FP
    │       │           │                                  curation → analysed corpus
    │       │           ▼                                  + per-stage shortlist tables
    │       │       stage_shortlists.csv
    │       │
    │       ├── figures/generate_all_figures.py        ← step 5b: publication figures
    │       │           │                                  (17-module master runner)
    │       │           ▼
    │       │       figures/fig_*.{pdf,png}
    │       │
    │       └── analysis/patent_analysis.py            ← step 5c (optional branch):
    │                   │                                  patent-landscape companion
    │                   ▼                                  (requires BigQuery auth)
    │               patents_strict_list.csv,
    │               patents_vs_publications_strict.csv
    │
    └── analysis/*.py                        (15+ standalone text-output analyses —
                                              geo, citation, venues, etc.)
```

## Reproducing the published results

You do **not** need Scopus credentials to reproduce anything in the paper. Clone
the dataset repository alongside this one and point `DATADIR` at it:

```bash
git clone https://github.com/ignaciosim/AI4Chips_SLR.git
git clone https://github.com/ignaciosim/AI4Chips_SLR_data.git
cd AI4Chips_SLR
ln -s ../AI4Chips_SLR_data/corpus corpus

make figures      # 22 figure scripts -> corpus/figures/*.png
make analysis     # text analyses to stdout
```

`DATADIR` defaults to `corpus`, so no argument is needed. The Scopus retrieval
stage will not fire when the corpus is already present — its prerequisites are
order-only precisely so that a fresh clone cannot trigger a multi-hour re-fetch.
Use `make refetch` if you actually want to re-retrieve.

`make patents` is the exception: it queries BigQuery and needs Google Cloud
credentials. The patent artefacts it would produce are already in the dataset
repository.

> **Run scripts through the Makefile, or pass `--datadir` explicitly.** Many
> scripts under `analysis/` carry a hard-coded default data directory from the
> run they were written against. Invoked bare they will read the wrong corpus,
> or fail if that directory is absent. The Makefile always passes `--datadir`.

---

## Runbook (one-command pipeline)

From a fresh clone, the whole Scopus pipeline is a `make` away. The
Makefile encodes the stage order, tracks output timestamps (so re-runs
skip fresh stages), and scopes all outputs to a per-run data directory.

```bash
# 0. Install pinned dependencies into a virtualenv.
make setup
source .venv/bin/activate

# 1. Verify credentials and dependencies before spending hours on fetch.
make preflight

# 2. Run the whole Scopus pipeline end-to-end into a new data directory.
make all DATADIR=corpus

# 3. Optional companion analyses.
make analysis DATADIR=corpus          # text-output analyses
make patents  DATADIR=corpus          # patent-landscape (BigQuery)
```

`make all` runs `fetch → merge → classify → final → shortlist → figures`
in order. Outputs accumulate inside `corpus/`; the master figures
land in `corpus/figures/`. Running `make all` a second time is a
no-op (the Makefile tracks output file timestamps), so you can safely
re-run to check status.

### Prerequisites

The `make setup` step installs every Python dependency; you only need
two external credentials:

| Credential | Needed for | How to provide |
|---|---|---|
| Scopus API key | `make fetch`, `make all` | `../config.json` with `{"scopus_api_key": "..."}` (override path with `CONFIG=`) |
| Google Cloud auth | `make patents` (optional) | `gcloud auth application-default login` — sets up BigQuery client |

The `make preflight` target sanity-checks both before running anything.

### Overridable Makefile variables

| Variable | Default | Purpose |
|---|---|---|
| `DATADIR` | `corpus` | Per-run data / output directory. `corpus` is the directory name used by the published dataset repo; pass your own run directory (e.g. `scopus_out13`) for a new pipeline run. |
| `CONFIG` | `../config.json` | Scopus API config |
| `VENUES` | `venues_eda.txt` | Venue allow-list |
| `START_YEAR` | `2015` | Retrieval window start |
| `END_YEAR` | `2026` | Retrieval window end |
| `MAX_PAGES` | `80` | Scopus pagination cap per phase |
| `GCP_PROJECT` | *(auto-detect)* | GCP project for BigQuery |

All are passed on the command line, e.g.:
`make all DATADIR=corpus START_YEAR=2018 END_YEAR=2025`.

### Housekeeping

`make clean DATADIR=corpus` removes derived outputs but preserves the
raw Scopus fetch (which is expensive to regenerate). `make nuke` removes
the entire per-run directory. `make -n all` prints the command chain as a
dry run without executing.

### Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `fetch_scopus.py` stalls at ~25 records | Scopus API rate limit | Re-run; the script resumes from the next page. Reduce `--max_pages` if needed. |
| `analysis/patent_analysis.py` raises `DefaultCredentialsError` | BigQuery auth missing | `gcloud auth application-default login`, then re-run `make patents`. |
| Figures missing citation counts | OpenAlex cache empty or stale | First run `python3 figures/fig_linguistic_terms.py` to warm the cache (standalone; not in `make all`). |

## Usage (individual scripts — low-level)

> Prefer `make <target>` from the RUNBOOK above. This section documents the
> underlying per-script CLIs for cases where you want to drive individual
> stages by hand (debugging, partial reruns, custom flag combinations).

### Prerequisites

```bash
pip install -r requirements.txt
```

### Step 1: Fetch from Scopus

```bash
# Basic (all phases, 2015–2026 window as used by the current paper corpus)
python fetch_scopus.py --config ../config.json \
    --venues_file venues_eda.txt \
    --start_year 2015 --end_year 2026 --max_pages 80 \
    --outdir corpus

# Narrow window for a quick revision run
python fetch_scopus.py --config ../config.json \
    --venues_file venues_eda.txt \
    --start_year 2019 --end_year 2025 --max_pages 20 \
    --outdir corpus
```

Output: `corpus/raw_scopus_{design,fabrication,packaging,transit,in_field,disposal}.jsonl`

### Step 2: Merge and deduplicate

```bash
python merge_scopus.py corpus/
```

Output: `corpus/raw_scopus_all.{csv,jsonl}` (deduplicated union
of the six per-phase files from Step 1).

### Step 3: Classify + tag methods

```bash
# From merged CSV (title-only classification)
python classify_scopus.py corpus/raw_scopus_all.csv

# From JSONL directory (title + abstract — more accurate if abstracts available)
python classify_scopus.py corpus/ --from_jsonl

# Keep deep_learning tag when LLM is also detected
python classify_scopus.py corpus/raw_scopus_all.csv --keep_dl_with_llm
```

Output: `classified_scopus.csv`, `ai_methods_long.csv`, the `pivot_*.csv`
set, and `classification_summary.txt` — all inside `corpus/`.

### Step 4: Extract the high-confidence AI-for-Chips corpus

```bash
python create_final_high_confidence_only.py corpus
```

Reads `classified_scopus.csv` plus the raw JSONL files for affiliation
metadata, keeps only papers the classifier labelled `ai_for_chips` at
high confidence, removes the GaN-material false positives (a dedicated
filter for the "generative adversarial network" vs. "gallium nitride"
lexical collision), and writes the downstream-ready corpus:

Output: `corpus/final_ai4chips_high_only.{csv,json}` — the input
for every analysis script, every figure, and the patent-landscape
companion. Corpus size depends on the retrieval window, the venue
allow-list, and Scopus index state at fetch time.

### Step 5: Curated per-stage shortlist (surveys + manual FPs removed)

```bash
python analysis/generate_stage_shortlist.py --datadir corpus
```

Applies editorial curation on top of Step 4's corpus: removes survey /
review / tutorial papers by title keyword, excludes manually-flagged
false positives and chips-for-AI entries (via `EXCLUDE_DOIS` in the
script), applies cross-lifecycle stage reassignments, and emits per-phase
shortlist tables scored by a blended ranking (top-cited anchors +
method-and-task-diverse exemplars + high-cites-per-year recent papers +
2026 papers regardless of citation count + editorial promotions).

Output: `corpus/stage_shortlists.csv` — the basis for the paper's
per-stage shortlist tables.

### Optional: Export OWL ontology

```bash
python slr_ontology.py
# → silicon_lifecycle_ontology.owl (importable in Protégé)
```

## Output files

All paths below are relative to the per-run data directory (`DATADIR`,
default `corpus/`).

### Stage 1–2 — fetch + merge

| File | Description |
|---|---|
| `raw_scopus_<phase>.{jsonl,csv}` | Per-lifecycle-phase raw retrieval (6 phases) |
| `raw_scopus_all.{csv,jsonl}`     | Deduplicated union of all phases |
| `raw_scopus_venue_counts.csv`    | Per-venue retrieval counts (sanity check) |
| `scopus_counts_by_stage_year.csv`| Retrieval volume by phase × year |

### Stage 3 — classify

| File | Description |
|---|---|
| `classified_scopus.csv`                    | Per-paper: classification, confidence, method tags, entity matches |
| `ai_methods_long.csv`                      | Long-form: one row per (paper, method) pair |
| `pivot_ai_methods_counts.csv`              | Method × year counts (all papers) |
| `pivot_ai_methods_share.csv`               | Method × year normalized shares |
| `pivot_ai_methods_by_stage.csv`            | Method × stage × year |
| `pivot_ai_methods_counts_ai4chips_only.csv`| Method × year counts (ai_for_chips + both) |
| `classification_summary.txt`               | Human-readable summary with precision estimate |

### Stage 4 — high-confidence filter

| File | Description |
|---|---|
| `final_ai4chips_high_only.{csv,json}` | High-confidence AI-for-Chips corpus, post-GaN-FP filter. Source for all downstream analyses and figures. |

### Stage 5a — curated shortlist

| File | Description |
|---|---|
| `stage_shortlists.csv` | Per-lifecycle-phase curated shortlist tables (surveys and manual-FP entries removed). Basis for the paper's headline tables. |

### Stage 5b — figures (in `DATADIR/figures/`)

`figures/fig_*.{pdf,png}` — publication figures (pub-volume, AI methods,
chip tasks, analog/digital split, commercial apps, venues, geography,
citations, method × country, method × task, emerging topics, growth model,
task combinations, keyword × country, AI-for-Chips vs. field geography,
linguistic terms, etc.). See
`figures/generate_all_figures.py` for the full list.

### Stage 5c — patent-landscape companion (optional)

| File | Description |
|---|---|
| `patents_strict_list.csv`                          | Per-family audit list of strict AI-for-Chips patents (CPC-conjunction ∧ AI-method title keyword) |
| `patents_strict_list_chipkw_sensitivity.csv`       | Higher-recall sensitivity cut (chip-keyword title filter) |
| `patents_vs_publications_strict.csv`               | Per-company patent count vs. SLR journal publications (counted against the curated corpus) |
| `patents_vs_publications.csv`                      | Loose OR-based CPC magnitude reference |
| `case_study_patents.csv`                           | Targeted inventor probes for named shortlist papers |

## Classification labels

| Label          | Meaning                                             | Ontology pattern                        |
|----------------|-----------------------------------------------------|-----------------------------------------|
| `ai_for_chips` | AI/ML used as a **tool** for chip design            | `methodAppliedToTask(AIMethod, Task)`   |
| `chips_for_ai` | Chip designed as a **product** for AI workloads     | `artifactForWorkload(Artifact, Workload)` |
| `both`         | Paper addresses both directions                     | Method + Task + Artifact detected       |
| `ambiguous`    | AI method detected but no clear target              | Method only, no task or artifact        |
| `unclassified` | No ontology pattern matched                         | Needs manual screening                  |

## Extending the ontology

All vocabulary lives in `slr_ontology.py`. To add a new concept:

```python
# Add a new AI method
AI_METHODS["diffusion_models"] = OntologyClass(
    key="diffusion_models",
    label="Diffusion Models",
    surface_forms=[
        "diffusion model", "denoising diffusion", "score-based",
        "stable diffusion", "ddpm",
    ],
)

# Add a new chip design task
CHIP_DESIGN_TASKS["emi_analysis"] = OntologyClass(
    key="emi_analysis",
    label="EMI Analysis",
    surface_forms=[
        "electromagnetic interference", "emi analysis",
        "emi simulation", "radiated emission",
    ],
)
```

Changes propagate to all scripts automatically on next run.

---

## License

Source code in this repository is released under the [MIT License](LICENSE) © 2026 Ignacio Chechile.

The companion dataset — [AI4Chips_SLR_data](https://github.com/ignaciosim/AI4Chips_SLR_data) — is released separately under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) for the curated annotations, with the underlying Scopus records remaining subject to Elsevier's API terms of use.

If you use this pipeline or the resulting corpus in academic work, please cite the accompanying paper (citation forthcoming).
