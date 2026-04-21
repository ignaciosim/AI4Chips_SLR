"""
Create final dataset using only high-confidence ai4chips papers.
Excludes ambiguous papers and filters out GaN semiconductor false positives.

Usage: python create_final_high_confidence_only.py [outdir]
       default outdir: scopus_out7
"""

import pandas as pd
import json
import re
import sys
from pathlib import Path

outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('scopus_out7')
print(f"Working directory: {outdir}")

df_all = pd.read_csv(outdir / 'classified_scopus.csv')
df = df_all[(df_all['classification'] == 'ai_for_chips') &
            (df_all['confidence'] == 'high')].copy()
print(f"High-confidence ai4chips papers: {len(df)}")

def is_gan_material_false_positive(row):
    """Check if 'gan' match is actually GaN semiconductor material."""
    title = str(row.get('title', '')).lower()
    methods = str(row.get('method_tags', ''))

    if 'generative_adversarial' not in methods:
        return False

    # Check for valid GAN neural network context first
    gan_context_words = [
        'generative adversarial', 'adversarial network', 'adversarial net',
        'discriminator', 'image generation', 'synthesis using gan',
        'image synthesis', 'conditional gan', 'cgan', 'dcgan', 'wgan',
        'cyclegan', 'pix2pix', 'deep convolutional gan', 'style transfer',
    ]
    if any(word in title for word in gan_context_words):
        return False

    # GaN material patterns
    gan_material_patterns = [
        r'algan', r'ingan', r'gan hemt', r'gan-on', r'gan power',
        r'gan transistor', r'gan device', r'gan led', r'gan driver',
        r'gan mosfet', r'gan fet', r'p-gan', r'gan-based power',
        r'gan mmic', r'gan amplifier', r'gan monolithic',
        r'gallium nitride', r'hemt', r'high electron mobility',
        r'gan converter', r'gan switch', r'gan-on-si', r'gan-on-sic',
        r'vertical gan', r'lateral gan', r'gan-based converter',
    ]

    for pattern in gan_material_patterns:
        if re.search(pattern, title):
            return True

    return False

# Filter out GaN false positives
df['is_gan_fp'] = df.apply(is_gan_material_false_positive, axis=1)
gan_fps = df[df['is_gan_fp']]
clean_df = df[~df['is_gan_fp']].drop(columns=['is_gan_fp'])

print(f"GaN false positives removed: {len(gan_fps)}")
print(f"Final paper count: {len(clean_df)}")

# Sort by year
clean_df = clean_df.sort_values(by=['year', 'doc_id'], ascending=[True, True])

# Export CSV
csv_output = outdir / 'final_ai4chips_high_only.csv'
clean_df.to_csv(csv_output, index=False)
print(f"\nExported CSV to: {csv_output}")

# Create JSON with full metadata
doc_ids_needed = set(clean_df['doc_id'].tolist())

# Build classification lookup
classification_data = {}
for _, row in clean_df.iterrows():
    classification_data[row['doc_id']] = {
        'classification': row['classification'],
        'confidence': row['confidence'],
        'reasoning': row['reasoning'],
        'method_tags': row['method_tags'] if pd.notna(row['method_tags']) else None,
        'ai_methods': row['ai_methods'] if pd.notna(row['ai_methods']) else None,
        'chip_tasks': row['chip_tasks'] if pd.notna(row['chip_tasks']) else None,
        'hw_artifacts': row['hw_artifacts'] if pd.notna(row['hw_artifacts']) else None,
        'ai_workloads': row['ai_workloads'] if pd.notna(row['ai_workloads']) else None,
    }

# Extract metadata from raw JSONL
papers = []
with open(outdir / 'raw_scopus_all.jsonl', 'r') as f:
    for line in f:
        record = json.loads(line)
        entry = record.get('entry', {})
        eid = entry.get('eid')

        if eid in doc_ids_needed:
            paper = {
                'doc_id': eid,
                'stage': record.get('stage'),
                'year': record.get('year'),
                'title': entry.get('dc:title'),
                'creator': entry.get('dc:creator'),
                'publication': entry.get('prism:publicationName'),
                'doi': entry.get('prism:doi'),
                'volume': entry.get('prism:volume'),
                'issue': entry.get('prism:issueIdentifier'),
                'pages': entry.get('prism:pageRange'),
                'cover_date': entry.get('prism:coverDate'),
                'cited_by_count': entry.get('citedby-count'),
                'affiliations': entry.get('affiliation', []),
                'scopus_url': None,
                'abstract_url': entry.get('prism:url'),
                'slr_classification': classification_data[eid],
            }

            links = entry.get('link', [])
            for link in links:
                if link.get('@ref') == 'scopus':
                    paper['scopus_url'] = link.get('@href')
                    break

            papers.append(paper)

# Sort by year
papers_sorted = sorted(papers, key=lambda x: (x['year'], x['doc_id']))

# Write JSON
json_output = outdir / 'final_ai4chips_high_only.json'
with open(json_output, 'w') as f:
    json.dump(papers_sorted, f, indent=2)

print(f"Exported JSON to: {json_output}")
print(f"Total papers: {len(papers_sorted)}")

# Year distribution
print("\n--- Year Distribution ---")
year_counts = clean_df['year'].value_counts().sort_index()
for year, count in year_counts.items():
    print(f"  {year}: {count}")
