#!/usr/bin/env python3
"""Sync rbac/users.json to Cognito User Pool.

Reads the user registry from rbac/users.json and:
- Creates users in Cognito if they don't exist
- Adds users to the correct Cognito Group matching their role
- Disables users marked as inactive
- Idempotent: safe to re-run

Usage:
    python scripts/sync-users.py --user-pool-id eu-west-2_xxxxxxxx

Requires:
    - AWS credentials with cognito-idp admin permissions
    - boto3
"""

import argparse
import json
import sys
import boto3
from botocore.exceptions import ClientError


def load_users(path='rbac/users.json'):
    with open(path) as f:
        return json.load(f)['users']


def sync_user(cognito, pool_id, user):
    username = user['email']
    role = user['role']
    active = user.get('active', True)

    # Create user if not exists
    try:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            UserAttributes=[
                {'Name': 'email', 'Value': user['email']},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'name', 'Value': user['name']},
            ],
            DesiredDeliveryMediums=['EMAIL'],
            MessageAction='SUPPRESS'  # Don't send welcome email during sync
        )
        print(f'  Created user: {username}')
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f'  User exists: {username}')
        else:
            raise

    # Enable or disable based on active flag
    if active:
        cognito.admin_enable_user(UserPoolId=pool_id, Username=username)
    else:
        cognito.admin_disable_user(UserPoolId=pool_id, Username=username)
        print(f'  Disabled user: {username}')
        return

    # Remove from all groups first, then add to correct group
    all_groups = ['L1-operator', 'L2-engineer', 'L3-admin']
    for group in all_groups:
        try:
            cognito.admin_remove_user_from_group(
                UserPoolId=pool_id, Username=username, GroupName=group
            )
        except ClientError:
            pass

    # Add to the correct group
    cognito.admin_add_user_to_group(
        UserPoolId=pool_id, Username=username, GroupName=role
    )
    print(f'  Added {username} to group: {role}')


def main():
    parser = argparse.ArgumentParser(description='Sync rbac/users.json to Cognito')
    parser.add_argument('--user-pool-id', required=True, help='Cognito User Pool ID')
    parser.add_argument('--region', default='eu-west-2', help='AWS region')
    parser.add_argument('--users-file', default='rbac/users.json', help='Path to users.json')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without executing')
    args = parser.parse_args()

    users = load_users(args.users_file)
    print(f'Loaded {len(users)} users from {args.users_file}')

    if args.dry_run:
        for user in users:
            status = 'active' if user.get('active', True) else 'DISABLED'
            print(f'  [DRY RUN] {user["email"]} -> {user["role"]} ({status})')
        return

    cognito = boto3.client('cognito-idp', region_name=args.region)

    for user in users:
        print(f'Syncing: {user["name"]} ({user["email"]})')
        try:
            sync_user(cognito, args.user_pool_id, user)
        except Exception as e:
            print(f'  ERROR: {e}', file=sys.stderr)

    print('Sync complete.')


if __name__ == '__main__':
    main()
