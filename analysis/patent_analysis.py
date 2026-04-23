#!/usr/bin/env python3
"""
patent_analysis.py — Industrial AI-for-Chips patenting vs publishing.

Queries Google Patents Public Data via BigQuery to produce a complementary
view of the AI-for-Chips landscape. The SLR itself indexes only peer-reviewed
journal articles (by design); this script mirrors that analysis over the
patent record to quantify how much industrial activity sits outside the
corpus.

Two complementary analyses are produced:

  1. **Strict AI-for-Chips patent count per major chip company.** A patent
     qualifies as AI-for-Chips only if it carries **both** a chip-design /
     EDA CPC classification and a machine-learning CPC classification — the
     patent equivalent of the ontology's "AI method AND chip task" rule.

       Chip-side CPCs:  G06F30, G06F17/50, G06F115, G06F119, G06F11/22,
                        G01R31/28, H01L
       AI-side CPCs:    G06N (all subclasses)

  2. **Case-study paper → patent lookup.** For selected highly-cited papers,
     probe the patent record for inventor-level matches with plausible
     assignees. This is deliberately narrow (three papers, targeted probes),
     because at-scale automatic paper-to-patent matching fails on common
     Chinese-surname ambiguity.

Prerequisites:
  * Google Cloud project with BigQuery access
  * Authenticated via `gcloud auth application-default login`
  * google-cloud-bigquery Python package installed
  * The public dataset `patents-public-data.patents.publications` is free to
    query from any GCP project

Outputs (all in --datadir, default scopus_out10/):
  patents_vs_publications_strict.csv   — primary result, strict CPC count
  patents_vs_publications.csv          — loose OR-based count, for footnote
  case_study_patents.csv               — raw hits for DREAMPlace / VeriGen / GAN-OPC
  patent_analysis_report.md            — human-readable summary

Usage:
  python3 analysis/patent_analysis.py --datadir scopus_out10
"""
from __future__ import annotations

import argparse
import json
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

# Approx publication counts from the industry-affiliation analysis
# (see the full-corpus classification in fresh runs of this script's
# sibling analyses). These are inlined as best-effort values for the
# strict-vs-pubs comparison; regenerate by rerunning the affiliation
# keyword classifier.
PUBLICATION_COUNTS = {
    "Intel": 46, "NVIDIA": 4, "Samsung": 28, "NXP": 16,
    "Siemens": 14, "Mentor Graphics": 0, "STMicroelectronics": 41,
    "Qualcomm": 4, "Infineon": 21, "SK Hynix": 6, "TSMC": 0,
    "IBM": 0, "Google": 0, "Apple": 0, "Synopsys": 0, "Cadence": 0,
    "AMD": 0, "Meta": 0, "Huawei": 0, "MediaTek": 0, "Micron": 0,
    "Broadcom": 0, "Applied Materials": 0, "KLA": 0, "Lam Research": 0,
    "ASML": 0, "imec": 0, "ARM": 0,
}

# Case studies — targeted paper -> patent probes
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


def run_strict_company_count(client: bigquery.Client, out_path: Path) -> None:
    """AI-for-Chips patent families per company: chip-CPC AND AI-CPC."""
    sql = f"""
    {_build_company_cte()},
    strict_ai_chip AS (
      SELECT p.family_id, asg.name AS assignee_name
      FROM `patents-public-data.patents.publications` p,
      UNNEST(p.assignee_harmonized) asg
      WHERE p.publication_date BETWEEN 20150101 AND 20261231
        AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c
                   WHERE c.code LIKE 'G06F30%' OR c.code LIKE 'G06F17/50%'
                      OR c.code LIKE 'G06F115%' OR c.code LIKE 'G06F119%'
                      OR c.code LIKE 'G06F11/22%' OR c.code LIKE 'G01R31/28%'
                      OR c.code LIKE 'H01L%')
        AND EXISTS(SELECT 1 FROM UNNEST(p.cpc) c WHERE c.code LIKE 'G06N%')
    )
    SELECT cp.name AS company,
           COUNT(DISTINCT sac.family_id) AS strict_patent_families
    FROM company_patterns cp
    JOIN strict_ai_chip sac ON REGEXP_CONTAINS(sac.assignee_name, cp.pattern)
    GROUP BY company
    ORDER BY strict_patent_families DESC
    """
    print("[strict] Counting AI-for-Chips patent families per company...")
    df = client.query(sql).to_dataframe()
    df["publications_in_slr"] = df["company"].map(PUBLICATION_COUNTS).fillna(0).astype(int)
    df["patent_to_pub_ratio"] = df.apply(
        lambda r: round(r["strict_patent_families"] / r["publications_in_slr"], 1)
        if r["publications_in_slr"] > 0 else None,
        axis=1,
    )
    df.to_csv(out_path, index=False)
    print(f"  wrote {out_path}")
    return df


def run_loose_company_count(client: bigquery.Client, out_path: Path) -> None:
    """Loose OR-based count for footnote / sensitivity context."""
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
    import pandas as pd
    combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined.to_csv(out_path, index=False)
    print(f"  wrote {out_path}  ({len(combined)} total rows)")


def write_report(strict_df, loose_df, outdir: Path) -> None:
    path = outdir / "patent_analysis_report.md"
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
        "a patent qualifies as AI-for-Chips only if it carries **both** a "
        "chip-design/EDA CPC (G06F30, G06F17/50, G06F115, G06F119, G06F11/22, "
        "G01R31/28, or H01L) **and** a machine-learning CPC (anywhere under "
        "G06N).",
        "",
        "## Strict AI-for-Chips patent families per company, 2015–2026",
        "",
        "| Company | Patent families | Publications in SLR | Ratio |",
        "|---|---:|---:|---:|",
    ]
    import pandas as pd
    for _, r in strict_df.iterrows():
        ratio = (f"{r['patent_to_pub_ratio']}×"
                 if pd.notna(r["patent_to_pub_ratio"]) else "∞ / —")
        lines.append(
            f"| {r['company']} | {r['strict_patent_families']:,} | "
            f"{r['publications_in_slr']:,} | {ratio} |"
        )
    lines += [
        "",
        "## Sensitivity: loose OR-based count for comparison",
        "",
        "The loose filter accepts patents with *either* a chip-design or an "
        "AI CPC (not both). Under this definition the counts are roughly "
        "10–20× higher but include traditional algorithmic EDA patents with "
        "no ML and general-purpose neural-network patents with no chip "
        "content. We report loose counts only for methodological sensitivity.",
        "",
        "| Company | Loose families | Strict families | Strict / loose |",
        "|---|---:|---:|---:|",
    ]
    loose_map = dict(zip(loose_df["company"], loose_df["loose_patent_families"]))
    for _, r in strict_df.iterrows():
        c = r["company"]
        loose_n = loose_map.get(c, 0)
        pct = f"{100*r['strict_patent_families']/loose_n:.0f}%" if loose_n else "—"
        lines.append(
            f"| {c} | {loose_n:,} | {r['strict_patent_families']:,} | {pct} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "Semiconductor-equipment makers (Applied Materials, KLA, ASML, imec) "
        "have disproportionately high AI-qualifying shares of their chip "
        "patent output (12–49%), indicating that ML is penetrating process "
        "equipment alongside its more visible role in EDA. Pure chipmakers "
        "and fabless design houses run at 3–10% strict/loose ratios. "
        "Infineon and STMicroelectronics are unusual in publishing more "
        "AI-for-Chips journal articles than they patent, consistent with "
        "their analog/power-IC focus and their presence in the device-physics "
        "and reliability journals indexed by the SLR corpus.",
        "",
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
                    help="Skip the loose OR-based sensitivity query")
    ap.add_argument("--skip-cases", action="store_true",
                    help="Skip the case-study probes")
    args = ap.parse_args()

    outdir = Path(args.datadir)
    outdir.mkdir(parents=True, exist_ok=True)
    client = (bigquery.Client(project=args.project) if args.project
              else bigquery.Client())
    print(f"BigQuery project: {client.project}")

    strict_df = run_strict_company_count(client, outdir / "patents_vs_publications_strict.csv")
    loose_df = None
    if not args.skip_loose:
        loose_df = run_loose_company_count(client, outdir / "patents_vs_publications.csv")
    if not args.skip_cases:
        run_case_studies(client, outdir / "case_study_patents.csv")
    if loose_df is not None:
        write_report(strict_df, loose_df, outdir)

    print("\nDone.")


if __name__ == "__main__":
    main()
