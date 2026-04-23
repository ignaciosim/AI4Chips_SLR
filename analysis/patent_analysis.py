#!/usr/bin/env python3
"""
patent_analysis.py — Industrial AI-for-Chips patenting vs publishing.

Queries Google Patents Public Data via BigQuery to produce a complementary
view of the AI-for-Chips landscape. The SLR itself indexes only peer-reviewed
journal articles (by design); this script mirrors that analysis over the
patent record to quantify how much industrial activity sits outside the
corpus.

Three complementary artefacts are produced:

  1. **Strict AI-for-Chips patent list and per-company count.** A patent
     qualifies as AI-for-Chips only if *all three* of the following hold —
     the patent equivalent of the ontology's "AI method AND chip task" rule
     plus a title-level precision filter:

       (a) Chip-design / EDA CPC class present
              G06F30, G06F17/50, G06F115, G06F119, G06F11/22, G01R31/28
          (H01L deliberately excluded — too broad; catches AI-accelerator
          chip filings, power electronics, and process-equipment patents
          unrelated to AI-for-chip-design.)
       (b) Machine-learning CPC class present (any subclass of G06N)
       (c) The patent title explicitly names an AI method (see
           TITLE_METHOD_REGEX below)

     Outputs: `patents_strict_list.csv` (one row per family) and
     `patents_vs_publications_strict.csv` (aggregate per benchmark company).

  2. **Chip-keyword sensitivity cut.** A looser title filter (chip-domain
     keywords such as "semiconductor", "layout", "lithography", etc.) is
     applied in place of the AI-method title filter, preserving the CPC
     conjunction. This captures AI-for-Chips filings whose titles omit the
     method name (e.g., "Method and apparatus for ..."). Emitted for
     reviewer sensitivity analysis, not headline reporting.

     Output: `patents_strict_list_chipkw_sensitivity.csv`.

  3. **Case-study paper → patent lookup.** For selected highly-cited
     papers, probe the patent record for inventor-level matches with
     plausible assignees. Narrow by design — at-scale automatic
     paper-to-patent matching fails on common Chinese-surname ambiguity.

     Output: `case_study_patents.csv`.

A loose OR-based CPC count (`patents_vs_publications.csv`) is also produced
by default and retained only as a magnitude reference; it is not the
headline number and is not used in the paper paragraph.

Prerequisites:
  * Google Cloud project with BigQuery access
  * Authenticated via `gcloud auth application-default login`
  * google-cloud-bigquery Python package installed
  * The public dataset `patents-public-data.patents.publications` is free to
    query from any GCP project

Usage:
  python3 analysis/patent_analysis.py --datadir scopus_out10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from google.cloud import bigquery
except ImportError:
    sys.stderr.write("ERROR: google-cloud-bigquery not installed.\n"
                     "  pip install google-cloud-bigquery\n")
    sys.exit(1)


# ── Chip-company patterns (regex over assignee_harmonized.name) ───────────
COMPANY_PATTERNS = [
    ("Intel",                r"(?i)\bintel\b"),
    ("NVIDIA",               r"(?i)\bnvidia\b"),
    ("Samsung",              r"(?i)\bsamsung\b"),
    ("TSMC",                 r"(?i)(\btsmc\b|taiwan semiconductor)"),
    ("IBM",                  r"(?i)\b(ibm|international business machines)\b"),
    ("Synopsys",             r"(?i)\bsynopsys\b"),
    ("Cadence",              r"(?i)\bcadence\b"),
    ("Siemens",              r"(?i)\bsiemens\b"),
    ("Mentor Graphics",      r"(?i)mentor graphics"),
    ("Google",               r"(?i)(\bgoogle\b|alphabet)"),
    ("Apple",                r"(?i)\bapple\b"),
    ("Meta",                 r"(?i)(meta platforms|\bfacebook\b)"),
    ("Qualcomm",             r"(?i)\bqualcomm\b"),
    ("AMD",                  r"(?i)(\bamd\b|advanced micro devices)"),
    ("ARM",                  r"(?i)\barm (ltd|limited|holdings)\b"),
    ("Huawei",               r"(?i)\bhuawei\b"),
    ("MediaTek",             r"(?i)mediatek"),
    ("SK Hynix",             r"(?i)(sk hynix|\bhynix\b)"),
    ("Micron",               r"(?i)\bmicron\b"),
    ("STMicroelectronics",   r"(?i)stmicroelectronics"),
    ("Infineon",             r"(?i)infineon"),
    ("NXP",                  r"(?i)\bnxp\b"),
    ("Broadcom",             r"(?i)broadcom"),
    ("Applied Materials",    r"(?i)applied materials"),
    ("KLA",                  r"(?i)(kla\-?tencor|\bkla\b)"),
    ("Lam Research",         r"(?i)lam research"),
    ("ASML",                 r"(?i)\basml\b"),
    ("imec",                 r"(?i)\bimec\b"),
]

PUBLICATION_COUNTS = {
    "Intel": 46, "NVIDIA": 4, "Samsung": 28, "NXP": 16,
    "Siemens": 14, "Mentor Graphics": 0, "STMicroelectronics": 41,
    "Qualcomm": 4, "Infineon": 21, "SK Hynix": 6, "TSMC": 0,
    "IBM": 0, "Google": 0, "Apple": 0, "Synopsys": 0, "Cadence": 0,
    "AMD": 0, "Meta": 0, "Huawei": 0, "MediaTek": 0, "Micron": 0,
    "Broadcom": 0, "Applied Materials": 0, "KLA": 0, "Lam Research": 0,
    "ASML": 0, "imec": 0, "ARM": 0,
}

# CPC-conjunction filter (shared by strict and sensitivity cuts).
# H01L deliberately excluded — see module docstring.
CHIP_CPC_WHERE = (
    "c.code LIKE 'G06F30%' OR c.code LIKE 'G06F17/50%' "
    "OR c.code LIKE 'G06F115%' OR c.code LIKE 'G06F119%' "
    "OR c.code LIKE 'G06F11/22%' OR c.code LIKE 'G01R31/28%'"
)
AI_CPC_WHERE = "c.code LIKE 'G06N%'"

# Title-level precision filter: the patent title must explicitly name an AI
# method. This is what takes the count from ~155 (CPC + chip-keywords) down
# to ~48 (CPC + method-names). See patents_strict_list_chipkw_sensitivity.csv
# for the broader alternative.
TITLE_METHOD_REGEX = (
    r"(machine learning|artificial intelligence|\bai[- ]based\b|"
    r"neural network|deep learning|reinforcement learning|"
    r"graph neural|generative adversarial|\bgan[- ]|"
    r"transformer[- ]based|large language model|\bllm[- ]|"
    r"convolutional|recurrent neural|\bcnn[- ]|\brnn[- ]|\blstm\b|"
    r"bayesian optimization|gaussian process|"
    r"active learning|self-supervised|semi-supervised|"
    r"variational autoencoder|\bvae\b|diffusion model)"
)

# Sensitivity cut: a chip-domain keyword (broader than method names).
TITLE_CHIP_POS_REGEX = (
    r"(integrated circuit|semiconductor|wafer|die|transistor|mosfet|"
    r"finfet|cmos|ic design|chip design|chiplet|layout|placement|routing|"
    r"floorplan|synthesis|lithograph|mask|opc|optical proximity|"
    r"inverse lithograph|metrology|yield|defect|rtl|verilog|vhdl|netlist|"
    r"hdl|timing|\bic\b|eda|power grid|power delivery|pdn|ir drop|"
    r"clock tree|trojan|fab|fabric|scatterometry|post-silicon|silicon|"
    r"imaging system|overlay|bump)"
)
TITLE_CHIP_NEG_REGEX = (
    r"(battery|flood|drug|medical|genomic|pharmaceutical|"
    r"autonomous vehicle|autonomous drivin|traffic simulation|"
    r"traffic flow|robot(?!ic)|robotic)"
)

CASE_STUDIES = [
    {
        "paper":    "DREAMPlace (Lin 2021)",
        "doi":      "10.1109/tcad.2020.3003843",
        "inv_regex": r"(?i)(yibo lin|haoxing ren|khailany)",
        "title_regex": r"(?i)(placement|floorplan|routing|layout.*gpu|layout.*neural|crosstalk|accelerat)",
        "years":    (20170101, 20281231),
    },
    {
        "paper":    "VeriGen (Thakur 2024)",
        "doi":      "10.1145/3643681",
        "inv_regex": r"(?i)(shailja thakur|ramesh karri|siddharth garg|hammond pearce)",
        "title_regex": r"(?i)(verilog|rtl|hdl|language model|code generation|trojan|hardware security)",
        "years":    (20200101, 20281231),
    },
    {
        "paper":    "GAN-OPC (Yang 2020)",
        "doi":      "10.1109/tcad.2019.2939329",
        "inv_regex": r"(?i)(haoyu yang|bei yu)",
        "title_regex": r"(?i)(mask|opc|optical proximity|lithograph|layout pattern|hotspot)",
        "years":    (20180101, 20281231),
    },
]


def _build_company_cte() -> str:
    rows = ",\n    ".join(
        f"STRUCT('{name}' AS name, r'{pat}' AS pattern)"
        for name, pat in COMPANY_PATTERNS
    )
    return f"WITH company_patterns AS (SELECT * FROM UNNEST([\n    {rows}\n  ]))"


def _strict_list_sql(title_regex: str) -> str:
    """Per-family strict list with CPC conjunction and a title-regex filter."""
    return f"""
    {_build_company_cte()},
    strict_ai_chip AS (
      SELECT
        p.family_id,
        p.publication_number,
        CAST(p.publication_date AS STRING) AS earliest_date,
        asg.name AS assignee_name,
        p.title_localized[SAFE_OFFSET(0)].text AS title,
        p.country_code,
        (SELECT STRING_AGG(c.code, ';') FROM UNNEST(p.cpc) c) AS cpc_codes
      FROM `patents-public-data.patents.publications` p,
      UNNEST(p.assignee_harmonized) asg
      WHERE p.publication_date BETWEEN 20150101 AND 20261231
        AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c WHERE {CHIP_CPC_WHERE})
        AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c WHERE {AI_CPC_WHERE})
        AND REGEXP_CONTAINS(
              LOWER(p.title_localized[SAFE_OFFSET(0)].text),
              r'{title_regex}')
    ),
    first_per_family AS (
      SELECT
        cp.name AS matched_company,
        sac.family_id,
        ANY_VALUE(sac.publication_number) AS publication_number,
        MIN(sac.earliest_date) AS earliest_date,
        ANY_VALUE(sac.assignee_name) AS assignee,
        ANY_VALUE(sac.title) AS title,
        ANY_VALUE(sac.country_code) AS country_code,
        ANY_VALUE(sac.cpc_codes) AS cpc_codes
      FROM company_patterns cp
      JOIN strict_ai_chip sac
        ON REGEXP_CONTAINS(sac.assignee_name, cp.pattern)
      GROUP BY cp.name, sac.family_id
    )
    SELECT * FROM first_per_family
    ORDER BY matched_company, earliest_date DESC
    """


def run_strict_list(client: bigquery.Client, outdir: Path,
                    title_regex: str, out_name: str,
                    post_neg_regex: str | None = None) -> "pd.DataFrame":
    """Emit per-family strict list. Optionally drop titles that also match
    a negative regex (used only in the chip-keyword sensitivity cut)."""
    import pandas as pd
    print(f"[strict] Building per-family list → {out_name} ...")
    df = client.query(_strict_list_sql(title_regex)).to_dataframe()
    if post_neg_regex is not None and not df.empty:
        import re
        neg = re.compile(post_neg_regex, re.IGNORECASE)
        df = df[~df["title"].fillna("").str.contains(neg, regex=True)].reset_index(drop=True)
    path = outdir / out_name
    df.to_csv(path, index=False)
    print(f"  wrote {path}  ({len(df)} rows)")
    return df


def run_strict_company_count(outdir: Path, strict_df) -> "pd.DataFrame":
    """Aggregate the per-family list into a per-company table against the
    SLR publication counts. Covers the full 28-company benchmark set even
    if some companies have zero patent hits."""
    import pandas as pd
    counts = strict_df.groupby("matched_company").size().to_dict() if len(strict_df) else {}
    rows = []
    for name, _ in COMPANY_PATTERNS:
        n_pat = int(counts.get(name, 0))
        n_pub = PUBLICATION_COUNTS.get(name, 0)
        if n_pub == 0:
            ratio = "inf" if n_pat > 0 else "—"
        else:
            ratio = f"{n_pat / n_pub:.2f}"
        rows.append({
            "company": name,
            "strict_patent_families": n_pat,
            "publications_in_slr": n_pub,
            "patent_to_pub_ratio": ratio,
        })
    df = pd.DataFrame(rows).sort_values(
        by=["strict_patent_families", "publications_in_slr"],
        ascending=[False, False], ignore_index=True,
    )
    path = outdir / "patents_vs_publications_strict.csv"
    df.to_csv(path, index=False)
    print(f"  wrote {path}  ({len(df)} companies)")
    return df


def run_loose_company_count(client: bigquery.Client, out_path: Path) -> "pd.DataFrame":
    """Loose OR-based count, kept as magnitude reference only."""
    sql = f"""
    {_build_company_cte()},
    loose_ai_chip AS (
      SELECT p.family_id, asg.name AS assignee_name
      FROM `patents-public-data.patents.publications` p,
      UNNEST(p.assignee_harmonized) asg
      WHERE p.publication_date BETWEEN 20150101 AND 20261231
        AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c
                   WHERE c.code LIKE 'G06F30%' OR c.code LIKE 'G06F17/50%'
                      OR c.code LIKE 'G06N3%'   OR c.code LIKE 'G06F115%'
                      OR c.code LIKE 'G06F119%' OR c.code LIKE 'G06F11/22%'
                      OR c.code LIKE 'G01R31/28%')
    )
    SELECT cp.name AS company,
           COUNT(DISTINCT lac.family_id) AS loose_patent_families
    FROM company_patterns cp
    JOIN loose_ai_chip lac ON REGEXP_CONTAINS(lac.assignee_name, cp.pattern)
    GROUP BY company
    ORDER BY loose_patent_families DESC
    """
    print("[loose]  Counting OR-based AI-or-chip patent families per company...")
    df = client.query(sql).to_dataframe()
    df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}")
    return df


def run_case_studies(client: bigquery.Client, out_path: Path) -> None:
    """Targeted paper->patent lookups for a handful of highly-cited papers."""
    import pandas as pd
    all_rows = []
    for cs in CASE_STUDIES:
        print(f"[case]  Probing {cs['paper']}...")
        sql = f"""
        SELECT
          '{cs['paper']}' AS paper,
          '{cs['doi']}' AS paper_doi,
          p.publication_number,
          p.family_id,
          EXTRACT(YEAR FROM PARSE_DATE('%Y%m%d', CAST(p.publication_date AS STRING))) AS pub_year,
          p.title_localized[SAFE_OFFSET(0)].text AS title,
          ARRAY(SELECT x.name FROM UNNEST(p.assignee_harmonized) x) AS assignees,
          ARRAY(SELECT x FROM UNNEST(p.inventor) x) AS inventors,
          p.country_code
        FROM `patents-public-data.patents.publications` p
        WHERE p.publication_date BETWEEN {cs['years'][0]} AND {cs['years'][1]}
          AND EXISTS(SELECT 1 FROM UNNEST(p.inventor) i
                     WHERE REGEXP_CONTAINS(LOWER(i), r'{cs["inv_regex"]}'))
          AND REGEXP_CONTAINS(LOWER(p.title_localized[SAFE_OFFSET(0)].text),
                              r'{cs["title_regex"]}')
          AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c
                     WHERE c.code LIKE 'G06F30%' OR c.code LIKE 'G06F17/50%'
                        OR c.code LIKE 'G06N3%'  OR c.code LIKE 'G06F115%'
                        OR c.code LIKE 'H01L%')
        ORDER BY p.publication_date DESC
        LIMIT 30
        """
        df = client.query(sql).to_dataframe()
        if not df.empty:
            df["assignees"] = df["assignees"].apply(
                lambda xs: "; ".join(list(xs)[:3]) if xs is not None else "")
            df["inventors"] = df["inventors"].apply(
                lambda xs: "; ".join(list(xs)[:6]) if xs is not None else "")
        all_rows.append(df)
        print(f"         found {len(df)} patent rows")
    combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined.to_csv(out_path, index=False)
    print(f"  wrote {out_path}  ({len(combined)} total rows)")


def write_report(company_df, sens_n: int | None, loose_df, outdir: Path) -> None:
    path = outdir / "patent_analysis_report.md"
    import pandas as pd
    total_strict = int(company_df["strict_patent_families"].sum())
    lines = [
        "# Patent-landscape analysis for AI-for-Chips",
        "",
        "Companion analysis to the publication-based SLR. All counts are "
        "patent *families* (deduplicated across jurisdictions) from "
        "`patents-public-data.patents.publications` on 2015–2026 publication "
        "dates.",
        "",
        "## Criterion",
        "",
        "To match the SLR's \"AI method applied to a chip design task\" rule, "
        "a patent qualifies as AI-for-Chips only if *all three* conditions hold:",
        "",
        "1. Its Cooperative Patent Classification codes include a "
        "chip-design/EDA class (G06F30, G06F17/50, G06F115, G06F119, "
        "G06F11/22, or G01R31/28). H01L is deliberately excluded: it catches "
        "AI-accelerator chip patents (chips-for-AI), power electronics, and "
        "process-equipment filings whose AI content is unrelated to chip "
        "design.",
        "2. Its CPC codes include a machine-learning class (any subclass of "
        "G06N).",
        "3. Its title explicitly names an AI method — one of *artificial "
        "intelligence*, *machine learning*, *neural network*, *deep "
        "learning*, *reinforcement learning*, *graph neural*, *generative "
        "adversarial network*, *convolutional*, *recurrent*, *LSTM*, "
        "*transformer-based*, *LLM*, *variational autoencoder*, *Bayesian "
        "optimization*, *Gaussian process*, *active/self-supervised/"
        "semi-supervised learning*, or *diffusion model*.",
        "",
        "The title-keyword step is a precision filter: CPC-only filtering "
        "leaves residual false positives whose AI content appears in an "
        "unrelated claim or dependent patent. Requiring the method to be "
        "named in the title matches the rigour of the peer-reviewed journal "
        "corpus, where a paper earns an AI-for-Chips tag only when method "
        "and task co-occur in the title or abstract.",
        "",
        f"## Strict AI-for-Chips patent families per company, 2015–2026 "
        f"(total n = {total_strict})",
        "",
        "Per-family list: `patents_strict_list.csv`. Per-company aggregation: "
        "`patents_vs_publications_strict.csv`.",
        "",
        "| Company | Patent families | Publications in SLR | Patent-to-publication ratio |",
        "|---|---:|---:|---:|",
    ]
    for _, r in company_df.iterrows():
        ratio_s = r["patent_to_pub_ratio"]
        ratio_cell = ratio_s if ratio_s in ("inf", "—") else f"{ratio_s}×"
        lines.append(
            f"| {r['company']} | {r['strict_patent_families']} | "
            f"{r['publications_in_slr']} | {ratio_cell} |"
        )
    lines += [
        "",
        "## Sensitivity cuts",
        "",
    ]
    if sens_n is not None:
        lines += [
            f"**Chip-keyword title filter (n = {sens_n}).** Replaces the "
            f"method-name title regex with a chip-domain keyword set "
            f"(semiconductor / layout / lithography / mask / metrology / "
            f"yield / RTL / Verilog / etc., minus a negative list such as "
            f"battery / medical / autonomous vehicle). Captures filings "
            f"whose titles use "
            f"non-method-named conventions (e.g., \"Method and apparatus "
            f"for ...\"), at the cost of lower precision. Per-family list: "
            f"`patents_strict_list_chipkw_sensitivity.csv`.",
            "",
        ]
    if loose_df is not None:
        lines += [
            "**Loose OR-based CPC count.** Accepts patents with *either* a "
            "chip-design or an AI CPC (not both). Orders of magnitude higher "
            "than the strict count; kept only as a sanity-check reference "
            "for the corpus size. Per-company aggregation: "
            "`patents_vs_publications.csv`.",
            "",
            "| Company | Loose families | Strict families |",
            "|---|---:|---:|",
        ]
        loose_map = dict(zip(loose_df["company"], loose_df["loose_patent_families"]))
        for _, r in company_df.iterrows():
            c = r["company"]
            loose_n = int(loose_map.get(c, 0))
            lines.append(
                f"| {c} | {loose_n:,} | {r['strict_patent_families']} |"
            )
        lines += [""]
    lines += [
        "## Regenerate",
        "",
        "```",
        "python3 analysis/patent_analysis.py --datadir scopus_out10",
        "```",
        "",
    ]
    path.write_text("\n".join(lines))
    print(f"  wrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out10",
                    help="Output directory (default scopus_out10)")
    ap.add_argument("--project", default=None,
                    help="GCP project ID (default: auto-detected)")
    ap.add_argument("--skip-loose", action="store_true",
                    help="Skip the loose OR-based magnitude reference query")
    ap.add_argument("--skip-sensitivity", action="store_true",
                    help="Skip the chip-keyword sensitivity cut")
    ap.add_argument("--skip-cases", action="store_true",
                    help="Skip the case-study probes")
    args = ap.parse_args()

    outdir = Path(args.datadir)
    outdir.mkdir(parents=True, exist_ok=True)
    client = (bigquery.Client(project=args.project) if args.project
              else bigquery.Client())
    print(f"BigQuery project: {client.project}")

    strict_df = run_strict_list(
        client, outdir,
        title_regex=TITLE_METHOD_REGEX,
        out_name="patents_strict_list.csv",
    )
    company_df = run_strict_company_count(outdir, strict_df)

    sens_n = None
    if not args.skip_sensitivity:
        sens_df = run_strict_list(
            client, outdir,
            title_regex=TITLE_CHIP_POS_REGEX,
            out_name="patents_strict_list_chipkw_sensitivity.csv",
            post_neg_regex=TITLE_CHIP_NEG_REGEX,
        )
        sens_n = len(sens_df)

    loose_df = None
    if not args.skip_loose:
        loose_df = run_loose_company_count(
            client, outdir / "patents_vs_publications.csv"
        )

    if not args.skip_cases:
        run_case_studies(client, outdir / "case_study_patents.csv")

    write_report(company_df, sens_n, loose_df, outdir)

    print("\nDone.")


if __name__ == "__main__":
    main()
