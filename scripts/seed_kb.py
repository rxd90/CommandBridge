#!/usr/bin/env python3
"""Seed the KB DynamoDB table from existing runbook markdown files.

Parses YAML frontmatter and markdown content from docs/runbooks/*.md
and inserts them as version 1 articles into the KB table.

Usage:
    python scripts/seed_kb.py [--table TABLE_NAME] [--dir RUNBOOKS_DIR]
"""

import argparse
import boto3
import glob
import os
import re
import time
import yaml


def parse_frontmatter(filepath):
    """Parse YAML frontmatter and markdown body from a file."""
    with open(filepath, 'r') as f:
        text = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
    if not match:
        return None, text

    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        meta = {}

    body = match.group(2).strip()
    return meta, body


def slugify(title):
    """Convert a title to a URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def seed(table_name, runbooks_dir):
    """Seed articles from runbook markdown files."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    files = sorted(glob.glob(os.path.join(runbooks_dir, '*.md')))
    if not files:
        print(f'No .md files found in {runbooks_dir}')
        return

    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    seeded = 0

    for filepath in files:
        meta, content = parse_frontmatter(filepath)
        if not meta or 'title' not in meta:
            print(f'  SKIP {filepath} (no frontmatter/title)')
            continue

        article_id = slugify(meta['title'])
        title = meta['title']
        service = meta.get('service', '')
        owner = meta.get('owner', '')
        category = meta.get('category', '')
        tags = meta.get('tags', [])
        last_reviewed = meta.get('last_reviewed', now[:10])

        if isinstance(last_reviewed, str):
            pass
        else:
            last_reviewed = str(last_reviewed)

        item = {
            'id': article_id,
            'version': 1,
            'title': title,
            'slug': article_id,
            'service': service,
            'owner': owner,
            'category': category,
            'tags': tags,
            'last_reviewed': last_reviewed,
            'content': content,
            'created_at': now,
            'created_by': 'seed-script',
            'updated_at': now,
            'updated_by': 'seed-script',
            'is_latest': 'true',
            'title_lower': title.lower(),
            'service_lower': service.lower(),
            'owner_lower': owner.lower(),
            'tags_lower': ','.join(t.lower() for t in (tags or [])),
        }

        table.put_item(Item=item)
        print(f'  OK  {article_id} ({title})')
        seeded += 1

    print(f'\nSeeded {seeded} articles into {table_name}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed KB table from runbook markdown files')
    parser.add_argument('--table', default=os.environ.get('KB_TABLE', 'commandbridge-dev-kb'),
                        help='DynamoDB table name')
    parser.add_argument('--dir', default=os.path.join(os.path.dirname(__file__), '..', 'docs', 'runbooks'),
                        help='Directory containing runbook .md files')
    args = parser.parse_args()

    print(f'Seeding KB table: {args.table}')
    print(f'Runbooks dir: {os.path.abspath(args.dir)}\n')
    seed(args.table, args.dir)
