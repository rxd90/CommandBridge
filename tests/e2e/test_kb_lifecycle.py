"""E2E tests for Knowledge Base article lifecycle.

Tests the full CRUD lifecycle: create -> read -> update -> versions -> delete,
all through the real handler with real DynamoDB operations.
"""

import json

import pytest

from tests.e2e.conftest import seed_user, call_handler

L2_EMAIL = 'l2@gov.scot'
L3_EMAIL = 'l3@gov.scot'


class TestKBLifecycleE2E:
    """Full KB article lifecycle through the handler."""

    def test_full_article_lifecycle(self, e2e):
        """Create -> Read -> Update -> List versions -> Delete -> 404."""
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')

        # 1. Create
        resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={
                'title': 'Login Failures',
                'service': 'identity',
                'owner': 'Platform Team',
                'category': 'Troubleshooting',
                'tags': ['login', 'auth'],
                'content': '## Step 1\nCheck Cognito logs.',
            },
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 201
        article = resp['parsed_body']['article']
        article_id = article['id']
        assert article['title'] == 'Login Failures'
        assert article['version'] == 1
        assert article['service'] == 'identity'

        # 2. Read
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['article']['content'] == '## Step 1\nCheck Cognito logs.'

        # 3. Update (creates version 2)
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'PUT',
            body={
                'content': '## Step 1\nCheck Cognito logs.\n## Step 2\nReview WAF rules.',
            },
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['article']['version'] == 2

        # 4. List versions
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}/versions', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 200
        versions = resp['parsed_body']['versions']
        assert len(versions) == 2

        # 5. Get version 1 (original content preserved)
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}/versions/1', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 200
        assert resp['parsed_body']['article']['content'] == '## Step 1\nCheck Cognito logs.'

        # 6. Delete (requires L3)
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'DELETE',
            email=L3_EMAIL, groups=['L3-admin'],
        )
        assert resp['statusCode'] == 200

        # 7. Verify deleted
        resp = call_handler(
            e2e['handler'], f'/kb/{article_id}', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 404

    def test_kb_list_with_search(self, e2e):
        """Create articles and verify search filtering works."""
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')

        # Create two articles
        call_handler(
            e2e['handler'], '/kb', 'POST',
            body={
                'title': 'MFA Troubleshooting',
                'service': 'identity',
                'owner': 'Security Team',
                'content': 'MFA guide',
                'tags': ['mfa', 'security'],
            },
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        call_handler(
            e2e['handler'], '/kb', 'POST',
            body={
                'title': 'Cache Purge Guide',
                'service': 'cache',
                'owner': 'Platform Team',
                'content': 'How to purge',
                'tags': ['cache', 'operations'],
            },
            email=L2_EMAIL, groups=['L2-engineer'],
        )

        # Search for "MFA"
        resp = call_handler(
            e2e['handler'], '/kb', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
            query_params={'search': 'mfa'},
        )
        assert resp['statusCode'] == 200
        articles = resp['parsed_body']['articles']
        assert len(articles) == 1
        assert articles[0]['title'] == 'MFA Troubleshooting'

    def test_kb_list_with_service_filter(self, e2e):
        """Filter articles by service."""
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')

        call_handler(
            e2e['handler'], '/kb', 'POST',
            body={'title': 'Identity Guide', 'service': 'identity',
                  'owner': 'Team', 'content': 'Content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        call_handler(
            e2e['handler'], '/kb', 'POST',
            body={'title': 'Cache Guide', 'service': 'cache',
                  'owner': 'Team', 'content': 'Content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )

        resp = call_handler(
            e2e['handler'], '/kb', 'GET',
            email=L2_EMAIL, groups=['L2-engineer'],
            query_params={'service': 'cache'},
        )
        assert resp['statusCode'] == 200
        articles = resp['parsed_body']['articles']
        assert len(articles) == 1
        assert articles[0]['service'] == 'cache'

    def test_update_nonexistent_returns_404(self, e2e):
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')

        resp = call_handler(
            e2e['handler'], '/kb/nonexistent-article', 'PUT',
            body={'content': 'Updated'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 404

    def test_create_duplicate_slug_returns_409(self, e2e):
        """Creating an article with the same slug returns 409."""
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')

        resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={'title': 'Unique Article', 'service': 'test',
                  'owner': 'Team', 'content': 'Content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 201

        # Same title -> same slug -> conflict
        resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={'title': 'Unique Article', 'service': 'test',
                  'owner': 'Team', 'content': 'Different content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        assert resp['statusCode'] == 409

    def test_kb_operations_create_audit_entries(self, e2e):
        """KB create, update, delete all write audit entries."""
        seed_user(e2e['users_table'], L2_EMAIL, 'L2 User', 'L2-engineer')
        seed_user(e2e['users_table'], L3_EMAIL, 'L3 User', 'L3-admin')

        # Create
        resp = call_handler(
            e2e['handler'], '/kb', 'POST',
            body={'title': 'Audited Article', 'service': 'test',
                  'owner': 'Team', 'content': 'Content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )
        article_id = resp['parsed_body']['article']['id']

        # Update
        call_handler(
            e2e['handler'], f'/kb/{article_id}', 'PUT',
            body={'content': 'Updated content'},
            email=L2_EMAIL, groups=['L2-engineer'],
        )

        # Delete
        call_handler(
            e2e['handler'], f'/kb/{article_id}', 'DELETE',
            email=L3_EMAIL, groups=['L3-admin'],
        )

        items = e2e['audit_table'].scan()['Items']
        actions = sorted([i['action'] for i in items])
        assert actions == ['kb-create', 'kb-delete', 'kb-update']
