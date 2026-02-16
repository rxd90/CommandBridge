#!/usr/bin/env python3
"""Seed the DynamoDB users table from rbac/users.json.

Reads the user registry and writes each user to the DynamoDB users table.
Idempotent: skips users that already exist to preserve their timestamps.

Usage:
    python3 scripts/seed_users.py --table commandbridge-prod-users
    python3 scripts/seed_users.py --table commandbridge-prod-users --dry-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def load_users(path='rbac/users.json'):
    with open(path) as f:
        return json.load(f)['users']


def seed_user(table, user):
    now = datetime.now(timezone.utc).isoformat()
    item = {
        'email': user['email'],
        'name': user['name'],
        'role': user['role'],
        'team': user.get('team', ''),
        'active': user.get('active', True),
        'created_at': now,
        'updated_at': now,
        'updated_by': 'seed',
    }
    try:
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(email)',
        )
        status = 'active' if item['active'] else 'DISABLED'
        print(f'  {item["email"]} -> {item["role"]} ({status})')
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f'  {item["email"]} -> already exists, skipping')
            return False
        raise


def main():
    parser = argparse.ArgumentParser(description='Seed DynamoDB users table')
    parser.add_argument('--table', required=True, help='DynamoDB table name')
    parser.add_argument('--region', default='eu-west-2', help='AWS region')
    parser.add_argument('--users-file', default='rbac/users.json', help='Path to users.json')
    parser.add_argument('--dry-run', action='store_true', help='Print without writing')
    args = parser.parse_args()

    users = load_users(args.users_file)
    print(f'Loaded {len(users)} users from {args.users_file}')

    if args.dry_run:
        for user in users:
            status = 'active' if user.get('active', True) else 'DISABLED'
            print(f'  [DRY RUN] {user["email"]} -> {user["role"]} ({status})')
        return

    dynamodb = boto3.resource('dynamodb', region_name=args.region)
    table = dynamodb.Table(args.table)

    created = 0
    skipped = 0
    for user in users:
        try:
            if seed_user(table, user):
                created += 1
            else:
                skipped += 1
        except Exception as e:
            print(f'  ERROR seeding {user["email"]}: {e}', file=sys.stderr)

    print(f'Done: {created} created, {skipped} already existed in {args.table}')


if __name__ == '__main__':
    main()
