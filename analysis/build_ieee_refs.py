#!/usr/bin/env python3
"""
Build IEEE-style reference entries for the shortlist papers and a
lookup table mapping common paper identifiers (Author Year) → reference number.

Reads:
  scopus_out10/final_ai4chips_high_only.json   — Scopus metadata
  scopus_out10/openalex_cache/openalex_ai4chips.json   — author name lists
  scopus_out10/stage_shortlists.md              — shortlist order

Writes:
  scopus_out10/references_ieee.md               — reference list, ready to paste
  scopus_out10/references_lookup.md             — Author Year → [N] table

Numbering starts at --start (default 10) so new references integrate with
existing manuscript references [1]–[9].
"""
from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path


VENUE_ABBREV = {
    "IEEE Transactions on Computer Aided Design of Integrated Circuits and Systems":
        "IEEE Trans. Comput.-Aided Des. Integr. Circuits Syst.",
    "IEEE Transactions on Very Large Scale Integration (VLSI) Systems":
        "IEEE Trans. Very Large Scale Integr. (VLSI) Syst.",
    "IEEE Transactions on Very Large Scale Integration VLSI Systems":
        "IEEE Trans. Very Large Scale Integr. (VLSI) Syst.",
    "IEEE Transactions on Semiconductor Manufacturing":
        "IEEE Trans. Semicond. Manuf.",
    "ACM Transactions on Design Automation of Electronic Systems":
        "ACM Trans. Des. Autom. Electron. Syst.",
    "Microelectronics Journal": "Microelectron. J.",
    "Microelectronics Reliability": "Microelectron. Rel.",
    "Integration the VLSI Journal": "Integration, the VLSI J.",
    "Integration": "Integration, the VLSI J.",
    "Journal of Industrial Information Integration": "J. Ind. Inf. Integr.",
}

MONTH = {
    "01": "Jan.", "02": "Feb.", "03": "Mar.", "04": "Apr.",
    "05": "May", "06": "Jun.", "07": "Jul.", "08": "Aug.",
    "09": "Sep.", "10": "Oct.", "11": "Nov.", "12": "Dec.",
}


def ieee_name(full_name: str) -> str:
    """'Shailja Thakur' → 'S. Thakur'; 'Brendan Dolan-Gavitt' → 'B. Dolan-Gavitt'."""
    full_name = full_name.strip()
    if not full_name:
        return ""
    # Handle mono-name case
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0]
    surname = parts[-1]
    given = parts[:-1]
    initials = []
    for g in given:
        # Hyphenated given name: Dae-Sun → D.-S.
        sub = g.split("-")
        initials.append("-".join(f"{s[0]}." for s in sub if s))
    return " ".join(initials) + " " + surname


def format_authors(authors: list[str]) -> str:
    formatted = [ieee_name(a) for a in authors if a.strip()]
    if not formatted:
        return ""
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    return ", ".join(formatted[:-1]) + ", and " + formatted[-1]


def abbrev_venue(venue: str) -> str:
    v = (venue or "").strip()
    return VENUE_ABBREV.get(v, v)


def month_from_date(cover_date: str) -> str:
    if not cover_date:
        return ""
    m = re.match(r"\d{4}-(\d{2})", cover_date)
    return MONTH.get(m.group(1), "") if m else ""


def paper_id(paper, author_lookup):
    """Return 'Surname I. YYYY' matching the Scopus dc:creator shorthand used
    in drafts (preserves initials for disambiguation between same-surname authors
    in the same year, e.g., 'Cheng C.K. 2021' vs 'Cheng K.C.C. 2021').
    Intentionally uses Scopus, not OpenAlex — OpenAlex preserves published
    author order, but drafts are keyed against Scopus's alphabetised creator."""
    creator = (paper.get("creator") or "?").strip()
    return f"{creator} {paper['year']}"


def format_ieee_entry(n: int, paper, authors: list[str]) -> str:
    title = paper["title"].strip().rstrip(".")
    venue = abbrev_venue(paper.get("publication") or "")
    vol = paper.get("volume") or ""
    issue = paper.get("issue") or ""
    pages = paper.get("pages") or ""
    year = paper["year"]
    month = month_from_date(paper.get("cover_date") or "")
    doi = (paper.get("doi") or "").strip()

    author_str = format_authors(authors) or (paper.get("creator") or "Unknown")
    parts = [f"[{n}] {author_str}, \u201C{title},\u201D *{venue}*"]
    trailing = []
    if vol:
        trailing.append(f"vol. {vol}")
    if issue:
        trailing.append(f"no. {issue}")
    if pages:
        trailing.append(f"pp. {pages}")
    if month:
        trailing.append(f"{month} {year}")
    elif year:
        trailing.append(str(year))
    if trailing:
        parts.append(", " + ", ".join(trailing))
    if doi:
        parts.append(f", doi: {doi}")
    parts.append(".")
    return "".join(parts)


def load_shortlist_dois(md_path):
    """Return list of (doi, stage, role) in shortlist order."""
    entries = []
    current_stage = None
    for line in Path(md_path).read_text().splitlines():
        if line.startswith("## "):
            current_stage = line[3:].split(" (")[0].strip()
            continue
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Role"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 9:
            continue
        role = parts[0]
        m = re.search(r"\[(10\.[^\]]+)\]", parts[-1])
        if m:
            entries.append((m.group(1).lower(), current_stage, role))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", default="scopus_out10")
    ap.add_argument("--start", type=int, default=10,
                    help="First reference number to use (default 10)")
    args = ap.parse_args()

    outdir = Path(args.datadir)
    scopus_data = {
        (p.get("doi") or "").lower(): p
        for p in json.loads((outdir / "final_ai4chips_high_only.json").read_text())
    }
    oa_cache = json.loads((outdir / "openalex_cache" / "openalex_ai4chips.json").read_text())

    # Build DOI → author list (from OpenAlex, preserves order)
    author_lookup = {}
    for doi_key, info in oa_cache.items():
        names = list((info.get("author_names") or {}).values())
        author_lookup[doi_key.lower()] = names

    # Shortlist order (first appearance)
    shortlist = load_shortlist_dois(outdir / "stage_shortlists.md")
    # Deduplicate while preserving order
    ordered = list(OrderedDict((doi, (stage, role)) for doi, stage, role in shortlist).items())

    # Generate entries
    entries = []
    lookup_rows = []
    for i, (doi, (stage, role)) in enumerate(ordered, start=args.start):
        p = scopus_data.get(doi)
        if not p:
            entries.append(f"[{i}] *DOI {doi} not found in Scopus JSON — fill manually.*")
            lookup_rows.append((f"DOI {doi}", i, "(missing metadata)"))
            continue
        authors = author_lookup.get(doi, [])
        entry = format_ieee_entry(i, p, authors)
        entries.append(entry)
        lookup_rows.append((paper_id(p, author_lookup), i, p["title"][:70]))

    # ── references_ieee.md ────────────────────────────────────────────────
    ref_path = outdir / "references_ieee.md"
    ref_lines = [
        "# IEEE References — shortlist papers",
        "",
        f"Entries {args.start} through {args.start + len(ordered) - 1} — "
        f"{len(ordered)} papers total, numbered in order of first appearance "
        "in `stage_shortlists.md`. Paste after the existing references "
        f"[1]–[{args.start - 1}] in the manuscript.",
        "",
    ]
    ref_lines.extend(entries)
    ref_path.write_text("\n".join(ref_lines) + "\n")
    print(f"Wrote {ref_path}")

    # ── references_lookup.md — maps Author Year → BibTeX key AND ref # ──
    lookup_path = outdir / "references_lookup.md"
    lookup_lines = [
        "# Citation lookup — Author Year → BibTeX key / Ref #",
        "",
        "Use this table to find the right citation for each paper mentioned "
        "in the drafts. The drafts (stage_shortlists.md, geo_paper_section.md, "
        "conclusion_digital_thread.md, stage_summaries.json) reference papers "
        "as *Author Year*. Column 2 is the BibTeX key (primary for "
        "Zotero/Mendeley/EndNote workflows), column 3 is the [N] number (if "
        "you paste references_ieee.docx directly).",
        "",
    ]

    # Pre-existing references from existing_refs.json
    existing_refs_path = outdir / "existing_refs.json"
    if existing_refs_path.exists():
        existing_refs = json.loads(existing_refs_path.read_text())
        lookup_lines += [
            "## Pre-existing references [1]\u2013[14]",
            "",
            "| Author Year | BibTeX key | Ref # | Title |",
            "|---|---|---|---|",
        ]
        for e in existing_refs:
            if e.get("placeholder"):
                continue
            # Derive Author Year shorthand from authors string.
            # Strip "et al." tails before parsing the first author.
            raw = re.sub(r"\s+et\s+al\.?", "", e["authors"])
            first_author = raw.split(",")[0].split(" and ")[0].strip()
            # "G. S. May" → surname is last token; show "May YYYY"
            surname = first_author.split()[-1] if first_author else "?"
            year = e["bibtex_key"][-4:] if e.get("bibtex_key") and e["bibtex_key"][-4:].isdigit() else "?"
            safe_title = e["title"].replace("|", r"\|")
            lookup_lines.append(
                f"| {surname} {year} | `{e.get('bibtex_key','')}` "
                f"| [{e['n']}] | {safe_title[:70]} |"
            )
        lookup_lines.append("")

    # Shortlist papers
    lookup_lines += [
        "## Shortlist papers [{}]\u2013[{}]".format(
            args.start, args.start + len(ordered) - 1),
        "",
        "| Author Year (as used in drafts) | BibTeX key | Ref # | Title |",
        "|---|---|---|---|",
    ]
    # Re-derive BibTeX keys to match build_ieee_refs_formatted.py's assignment
    # (FirstAuthorSurname + Year, with letter suffix on collision, keyed by
    # OpenAlex first author)
    keys_seen: set[str] = set()
    if existing_refs_path.exists():
        keys_seen.update(
            e["bibtex_key"] for e in existing_refs if "bibtex_key" in e
        )
    for i, (doi, _) in enumerate(ordered, start=args.start):
        p = scopus_data.get(doi)
        if not p:
            continue
        authors = author_lookup.get(doi, [])
        # Derive BibTeX key using same logic as build_ieee_refs_formatted.py
        if authors:
            surname = authors[0].split()[-1]
        else:
            creator = p.get("creator") or "Unknown"
            surname = re.split(r"[ ,]", creator.strip())[0]
        surname_clean = re.sub(r"[^A-Za-z]", "", surname) or "Anon"
        base = f"{surname_clean}{p['year']}"
        bib_key = base
        suffix = 0
        while bib_key in keys_seen:
            suffix += 1
            bib_key = f"{base}{chr(ord('a') + suffix - 1)}"
        keys_seen.add(bib_key)

        author_year = paper_id(p, author_lookup)
        safe_title = p["title"].replace("|", r"\|")[:70]
        lookup_lines.append(
            f"| {author_year} | `{bib_key}` | [{i}] | {safe_title} |"
        )

    lookup_path.write_text("\n".join(lookup_lines) + "\n")
    print(f"Wrote {lookup_path}")

    print(f"\n{len(ordered)} shortlist papers \u2192 references "
          f"[{args.start}]\u2013[{args.start + len(ordered) - 1}]")


if __name__ == "__main__":
    main()
