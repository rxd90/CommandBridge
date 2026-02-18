"""Knowledge Base handler route tests and KB data-access-layer tests.

Tests the KB routes in lambdas/actions/handler.py and the CRUD
operations in lambdas/shared/kb.py.
"""

import json
import os
import sys
import types
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

# ---------------------------------------------------------------------------
# Module-level mocks - must happen before importing handler / kb
# ---------------------------------------------------------------------------

# Patch shared.audit before handler import (same pattern as test_handler.py)
mock_audit = types.ModuleType('shared.audit')
mock_audit.log_action = MagicMock(return_value={'id': 'test', 'timestamp': 0})
sys.modules['shared.audit'] = mock_audit

# Patch shared.users before handler import (creates DynamoDB at module level)
mock_users = types.ModuleType('shared.users')
mock_users.get_user_role = MagicMock(return_value=None)
mock_users.get_user = MagicMock(return_value=None)
mock_users.list_users = MagicMock(return_value=[])
mock_users.update_user = MagicMock(return_value=None)
mock_users.VALID_ROLES = {'L1-operator', 'L2-engineer', 'L3-admin'}
sys.modules['shared.users'] = mock_users

# Set KB_TABLE env var before kb.py is imported (it reads at module level)
os.environ['KB_TABLE'] = 'commandbridge-test-kb'

from conftest import make_apigw_event


# ---------------------------------------------------------------------------
# DynamoDB table helper - creates the KB table with both GSIs
# ---------------------------------------------------------------------------

def _create_kb_table():
    """Create the KB DynamoDB table with hash key, range key, and GSIs."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName=os.environ['KB_TABLE'],
        KeySchema=[
            {'AttributeName': 'id', 'KeyType': 'HASH'},
            {'AttributeName': 'version', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'version', 'AttributeType': 'N'},
            {'AttributeName': 'is_latest', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'S'},
            {'AttributeName': 'service', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'latest-index',
                'KeySchema': [
                    {'AttributeName': 'is_latest', 'KeyType': 'HASH'},
                    {'AttributeName': 'updated_at', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'service-index',
                'KeySchema': [
                    {'AttributeName': 'service', 'KeyType': 'HASH'},
                    {'AttributeName': 'updated_at', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.meta.client.get_waiter('table_exists').wait(TableName=os.environ['KB_TABLE'])
    return table


# ===================================================================
# Part 1 - KB Handler Route Tests
# ===================================================================


class TestKBHandlerRoutes:
    """Test KB routes via lambda_handler + make_apigw_event."""

    # ── GET /kb ──────────────────────────────────────────────────

    @mock_aws
    def test_get_kb_returns_200_with_articles(self):
        """GET /kb returns 200 with an articles list."""
        _create_kb_table()
        # Re-point the kb module's table reference at the moto table
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        from actions.handler import lambda_handler

        # Seed one article
        _kb.create_article('Test Article', 'ServiceA', 'owner@test.com', ['tag1'], 'body', 'u@test.com')

        event = make_apigw_event('/kb', 'GET', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert 'articles' in body
        assert len(body['articles']) == 1

    @mock_aws
    def test_get_kb_search_returns_filtered(self):
        """GET /kb?search=X returns only matching articles."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('Alpha Guide', 'ServiceA', 'owner', [], 'content', 'u@test.com')
        _kb.create_article('Beta Guide', 'ServiceB', 'owner', [], 'content', 'u@test.com')

        event = make_apigw_event('/kb', 'GET', groups=['L1-operator'])
        event['queryStringParameters'] = {'search': 'alpha'}
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        articles = json.loads(resp['body'])['articles']
        assert len(articles) == 1
        assert articles[0]['title'] == 'Alpha Guide'

    # ── GET /kb/{id} ─────────────────────────────────────────────

    @mock_aws
    def test_get_kb_article_returns_200(self):
        """GET /kb/{id} returns 200 with the article."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('My Article', 'Svc', 'owner', [], 'content', 'u@test.com')

        event = make_apigw_event('/kb/my-article', 'GET', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['article']['title'] == 'My Article'

    @mock_aws
    def test_get_kb_article_not_found_returns_404(self):
        """GET /kb/{id} returns 404 when article does not exist."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        event = make_apigw_event('/kb/nonexistent', 'GET', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 404

    # ── GET /kb/{id}/versions ────────────────────────────────────

    @mock_aws
    def test_get_kb_versions_returns_list(self):
        """GET /kb/{id}/versions returns version list."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('Versioned', 'Svc', 'owner', [], 'v1', 'u@test.com')
        _kb.update_article('versioned', 'Versioned', 'Svc', 'owner', [], 'v2', 'u@test.com')

        event = make_apigw_event('/kb/versioned/versions', 'GET', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        versions = json.loads(resp['body'])['versions']
        assert len(versions) == 2

    # ── GET /kb/{id}/versions/{ver} ──────────────────────────────

    @mock_aws
    def test_get_kb_specific_version(self):
        """GET /kb/{id}/versions/{ver} returns the specific version."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('VerArticle', 'Svc', 'owner', [], 'v1 body', 'u@test.com')
        _kb.update_article('verarticle', 'VerArticle', 'Svc', 'owner', [], 'v2 body', 'u@test.com')

        event = make_apigw_event('/kb/verarticle/versions/1', 'GET', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        article = json.loads(resp['body'])['article']
        assert article['version'] == 1
        assert article['content'] == 'v1 body'

    # ── POST /kb ─────────────────────────────────────────────────

    @mock_aws
    def test_post_kb_l2_creates_article_201(self):
        """POST /kb with L2 group creates article and returns 201."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        event = make_apigw_event('/kb', 'POST',
            body={'title': 'New Article', 'service': 'SvcA', 'owner': 'team', 'content': 'hello'},
            groups=['L2-engineer'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 201
        body = json.loads(resp['body'])
        assert body['article']['title'] == 'New Article'
        assert body['article']['version'] == 1

    @mock_aws
    def test_post_kb_l1_returns_403(self):
        """POST /kb with L1 group returns 403 forbidden."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        event = make_apigw_event('/kb', 'POST',
            body={'title': 'Forbidden', 'service': 'S', 'owner': 'o', 'content': 'c'},
            groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 403

    @mock_aws
    def test_post_kb_missing_title_returns_400(self):
        """POST /kb without title returns 400."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        event = make_apigw_event('/kb', 'POST',
            body={'service': 'SvcA', 'content': 'no title'},
            groups=['L2-engineer'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 400
        assert 'title' in json.loads(resp['body'])['message'].lower()

    # ── PUT /kb/{id} ─────────────────────────────────────────────

    @mock_aws
    def test_put_kb_l2_updates_article_200(self):
        """PUT /kb/{id} with L2 group updates article and returns 200."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('Updatable', 'Svc', 'owner', [], 'original', 'u@test.com')

        event = make_apigw_event('/kb/updatable', 'PUT',
            body={'content': 'updated content'},
            groups=['L2-engineer'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200
        article = json.loads(resp['body'])['article']
        assert article['version'] == 2
        assert article['content'] == 'updated content'

    @mock_aws
    def test_put_kb_l1_returns_403(self):
        """PUT /kb/{id} with L1 group returns 403."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('NoEdit', 'Svc', 'owner', [], 'body', 'u@test.com')

        event = make_apigw_event('/kb/noedit', 'PUT',
            body={'content': 'hacked'},
            groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 403

    # ── DELETE /kb/{id} ──────────────────────────────────────────

    @mock_aws
    def test_delete_kb_l3_deletes_200(self):
        """DELETE /kb/{id} with L3 group deletes and returns 200."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('Deletable', 'Svc', 'owner', [], 'body', 'u@test.com')

        event = make_apigw_event('/kb/deletable', 'DELETE', groups=['L3-admin'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 200

        # Verify article is gone
        assert _kb.get_article('deletable') is None

    @mock_aws
    def test_delete_kb_l2_returns_403(self):
        """DELETE /kb/{id} with L2 group returns 403."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('Protected', 'Svc', 'owner', [], 'body', 'u@test.com')

        event = make_apigw_event('/kb/protected', 'DELETE', groups=['L2-engineer'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 403

    @mock_aws
    def test_delete_kb_l1_returns_403(self):
        """DELETE /kb/{id} with L1 group returns 403."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])
        from actions.handler import lambda_handler

        _kb.create_article('AlsoProtected', 'Svc', 'owner', [], 'body', 'u@test.com')

        event = make_apigw_event('/kb/alsoprotected', 'DELETE', groups=['L1-operator'])
        resp = lambda_handler(event, None)

        assert resp['statusCode'] == 403


# ===================================================================
# Part 2 - KB Data Access Layer Tests (shared/kb.py via moto)
# ===================================================================


class TestKBDataLayer:
    """Test kb.py CRUD functions directly against moto DynamoDB."""

    # ── create_article ───────────────────────────────────────────

    @mock_aws
    def test_create_article_correct_fields(self):
        """create_article populates all expected fields."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        article = _kb.create_article(
            title='Server Restart Procedure',
            service='Compute',
            owner='ops-team',
            tags=['runbook', 'compute'],
            content='# Steps\n1. Do it',
            user_email='author@test.com',
        )

        assert article is not None
        assert article['id'] == 'server-restart-procedure'
        assert article['slug'] == 'server-restart-procedure'
        assert article['version'] == 1
        assert article['title'] == 'Server Restart Procedure'
        assert article['service'] == 'Compute'
        assert article['owner'] == 'ops-team'
        assert article['tags'] == ['runbook', 'compute']
        assert article['content'] == '# Steps\n1. Do it'
        assert article['created_by'] == 'author@test.com'
        assert article['updated_by'] == 'author@test.com'
        assert 'created_at' in article
        assert 'updated_at' in article
        assert article['is_latest'] == 'true'
        # Internal _lower fields must be stripped from response
        assert 'title_lower' not in article
        assert 'service_lower' not in article

    @mock_aws
    def test_create_article_duplicate_slug_returns_none(self):
        """create_article returns None when slug already exists."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Duplicate Title', 'Svc', 'own', [], 'c', 'u@test.com')
        result = _kb.create_article('Duplicate Title', 'Svc', 'own', [], 'c2', 'u@test.com')

        assert result is None

    # ── get_article ──────────────────────────────────────────────

    @mock_aws
    def test_get_article_returns_latest_version(self):
        """get_article without version returns the latest version."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Evolving', 'Svc', 'own', [], 'v1', 'u@test.com')
        _kb.update_article('evolving', 'Evolving', 'Svc', 'own', [], 'v2', 'u@test.com')
        _kb.update_article('evolving', 'Evolving', 'Svc', 'own', [], 'v3', 'u@test.com')

        article = _kb.get_article('evolving')

        assert article is not None
        assert article['version'] == 3
        assert article['content'] == 'v3'

    # ── update_article ───────────────────────────────────────────

    @mock_aws
    def test_update_article_creates_new_version(self):
        """update_article bumps version and sets is_latest on new version."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Bumpy', 'Svc', 'own', [], 'original', 'u@test.com')
        updated = _kb.update_article('bumpy', 'Bumpy', 'Svc', 'own', [], 'revised', 'editor@test.com')

        assert updated['version'] == 2
        assert updated['content'] == 'revised'
        assert updated['updated_by'] == 'editor@test.com'
        assert updated['is_latest'] == 'true'

        # Old version should no longer be latest
        old = _kb.get_article('bumpy', version=1)
        assert old is not None
        assert old.get('is_latest') is None or old.get('is_latest') != 'true'

    # ── delete_article ───────────────────────────────────────────

    @mock_aws
    def test_delete_article_removes_all_versions(self):
        """delete_article removes every version of the article."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Doomed', 'Svc', 'own', [], 'v1', 'u@test.com')
        _kb.update_article('doomed', 'Doomed', 'Svc', 'own', [], 'v2', 'u@test.com')

        result = _kb.delete_article('doomed')

        assert result is True
        assert _kb.get_article('doomed') is None
        assert _kb.get_article('doomed', version=1) is None
        assert _kb.get_article('doomed', version=2) is None

    # ── list_articles ────────────────────────────────────────────

    @mock_aws
    def test_list_articles_returns_only_latest(self):
        """list_articles returns only latest versions, not old ones."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Article One', 'Svc', 'own', [], 'v1', 'u@test.com')
        _kb.update_article('article-one', 'Article One', 'Svc', 'own', [], 'v2', 'u@test.com')
        _kb.create_article('Article Two', 'Svc', 'own', [], 'v1', 'u@test.com')

        result = _kb.list_articles()

        # Should see exactly 2 articles (one per article, latest only)
        assert len(result['articles']) == 2
        # All returned articles should be the latest version
        for a in result['articles']:
            assert a.get('is_latest') == 'true'

    @mock_aws
    def test_list_articles_search_case_insensitive(self):
        """list_articles search is case-insensitive."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Kubernetes Cheatsheet', 'K8s', 'own', [], 'c', 'u@test.com')
        _kb.create_article('Docker Basics', 'Containers', 'own', [], 'c', 'u@test.com')

        # Search upper-case for a lower-cased title
        result = _kb.list_articles(search='KUBERNETES')
        assert len(result['articles']) == 1
        assert result['articles'][0]['title'] == 'Kubernetes Cheatsheet'

        # Search mixed case
        result2 = _kb.list_articles(search='dOcKeR')
        assert len(result2['articles']) == 1
        assert result2['articles'][0]['title'] == 'Docker Basics'

    # ── get_versions ─────────────────────────────────────────────

    @mock_aws
    def test_get_versions_returns_all_versions(self):
        """get_versions returns all versions for an article."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Multi', 'Svc', 'own', [], 'v1', 'u@test.com')
        _kb.update_article('multi', 'Multi', 'Svc', 'own', [], 'v2', 'u@test.com')
        _kb.update_article('multi', 'Multi', 'Svc', 'own', [], 'v3', 'u@test.com')

        versions = _kb.get_versions('multi')

        assert len(versions) == 3
        version_nums = sorted([v['version'] for v in versions])
        assert version_nums == [1, 2, 3]
        # Content should be stripped from version list
        for v in versions:
            assert 'content' not in v

    # ── slugify ──────────────────────────────────────────────────

    def test_slugify_basic(self):
        """slugify converts a plain title to a lowercase slug."""
        from shared import kb as _kb

        assert _kb.slugify('Hello World') == 'hello-world'

    def test_slugify_special_chars(self):
        """slugify strips special characters."""
        from shared import kb as _kb

        assert _kb.slugify('AWS EC2: Start/Stop Guide!') == 'aws-ec2-startstop-guide'

    def test_slugify_extra_whitespace(self):
        """slugify collapses whitespace and trims."""
        from shared import kb as _kb

        assert _kb.slugify('  Too   Many   Spaces  ') == 'too-many-spaces'

    def test_slugify_hyphens(self):
        """slugify collapses multiple hyphens into one."""
        from shared import kb as _kb

        assert _kb.slugify('a---b---c') == 'a-b-c'

    def test_slugify_mixed(self):
        """slugify handles mixed special characters and whitespace."""
        from shared import kb as _kb

        assert _kb.slugify('Kubernetes: Pod Restart (Runbook)') == 'kubernetes-pod-restart-runbook'

    # ── tags_lower search ─────────────────────────────────────────

    @mock_aws
    def test_create_article_sets_tags_lower(self):
        """create_article stores tags_lower as comma-joined lowercase string."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Tagged Article', 'Svc', 'owner', ['OIDC', 'Auth', 'Login'], 'body', 'u@test.com')

        # Read raw item to check internal field
        raw = _kb._table.get_item(Key={'id': 'tagged-article', 'version': 1})['Item']
        assert raw['tags_lower'] == 'oidc,auth,login'

    @mock_aws
    def test_update_article_sets_tags_lower(self):
        """update_article stores tags_lower on the new version."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Evolving Tags', 'Svc', 'owner', ['initial'], 'body', 'u@test.com')
        _kb.update_article('evolving-tags', 'Evolving Tags', 'Svc', 'owner', ['Redis', 'Cache'], 'updated', 'u@test.com')

        raw = _kb._table.get_item(Key={'id': 'evolving-tags', 'version': 2})['Item']
        assert raw['tags_lower'] == 'redis,cache'

    @mock_aws
    def test_search_by_tag_finds_article(self):
        """list_articles search matches against tags_lower field."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        _kb.create_article('Login Failures', 'Auth Service', 'Identity', ['oidc', 'jwks', 'token'], 'content', 'u@test.com')
        _kb.create_article('Cache Guide', 'Redis', 'Ops', ['redis', 'caching'], 'content', 'u@test.com')

        # Search by tag that is NOT in title/service/owner
        result = _kb.list_articles(search='jwks')
        assert len(result['articles']) == 1
        assert result['articles'][0]['title'] == 'Login Failures'

        # Search by another tag
        result2 = _kb.list_articles(search='caching')
        assert len(result2['articles']) == 1
        assert result2['articles'][0]['title'] == 'Cache Guide'

    @mock_aws
    def test_tags_lower_stripped_from_response(self):
        """tags_lower internal field is not returned in article responses."""
        _create_kb_table()
        from shared import kb as _kb
        _kb._table = boto3.resource('dynamodb', region_name='us-east-1').Table(os.environ['KB_TABLE'])

        article = _kb.create_article('Clean Response', 'Svc', 'owner', ['tag1'], 'body', 'u@test.com')
        assert 'tags_lower' not in article

        fetched = _kb.get_article('clean-response')
        assert 'tags_lower' not in fetched
