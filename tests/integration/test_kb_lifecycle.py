"""Integration tests for Knowledge Base CRUD, versioning, and search.

All articles use the 'inttest-' prefix and are cleaned up after session.
"""

import time

import pytest

from tests.integration.conftest import unique_title, L1_EMAIL, L2_EMAIL, L3_EMAIL


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestKBCreate:
    """POST /kb creates articles correctly."""

    def test_create_article_returns_201(self, api, l2_token):
        title = unique_title('create-basic')
        status, body = api.post('/kb', token=l2_token, body={
            'title': title,
            'service': 'test-service',
            'content': 'Integration test article content.',
        })
        assert status == 201
        assert 'article' in body

    def test_create_returns_article_with_all_fields(self, api, l2_token):
        title = unique_title('create-fields')
        status, body = api.post('/kb', token=l2_token, body={
            'title': title,
            'service': 'identity',
            'owner': 'Platform Team',
            'category': 'Backend',
            'tags': ['auth', 'test'],
            'content': '# Heading\n\nBody text.',
        })
        assert status == 201
        article = body['article']
        assert article['version'] == 1
        assert article['title'] == title
        assert 'id' in article
        assert 'slug' in article
        assert article['service'] == 'identity'
        assert article['owner'] == 'Platform Team'
        assert article['category'] == 'Backend'
        assert 'auth' in article['tags']
        assert 'created_at' in article
        assert 'updated_at' in article
        assert article['created_by'] == L2_EMAIL

    def test_create_slug_from_title(self, api, l2_token):
        title = unique_title('Slug Test Article')
        status, body = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'slug test',
        })
        assert status == 201
        slug = body['article']['id']
        # Slug should be lowercase with hyphens
        assert slug == slug.lower()
        assert ' ' not in slug

    def test_create_duplicate_slug_returns_409(self, api, l2_token):
        title = unique_title('dup-slug')
        api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'first',
        })
        status, body = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'second',
        })
        assert status == 409

    def test_create_missing_title_returns_400(self, api, l2_token):
        status, body = api.post('/kb', token=l2_token, body={
            'content': 'no title provided',
        })
        assert status == 400
        assert 'title' in body['message'].lower()

    def test_create_empty_title_returns_400(self, api, l2_token):
        status, body = api.post('/kb', token=l2_token, body={
            'title': '   ', 'content': 'whitespace title',
        })
        assert status == 400


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestKBRead:
    """GET /kb and GET /kb/{id} read operations."""

    def test_get_article_by_id(self, api, l2_token, l1_token):
        title = unique_title('read-get')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'Read test content.',
        })
        article_id = created['article']['id']

        status, body = api.get(f'/kb/{article_id}', token=l1_token)
        assert status == 200
        assert body['article']['content'] == 'Read test content.'

    def test_get_nonexistent_returns_404(self, api, l1_token):
        status, _ = api.get('/kb/inttest-no-such-article-xyz', token=l1_token)
        assert status == 404

    def test_list_articles_returns_latest_only(self, api, l2_token, l1_token):
        title = unique_title('list-latest')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'v1',
        })
        article_id = created['article']['id']

        # Update to create v2
        api.put(f'/kb/{article_id}', token=l2_token, body={
            'content': 'v2 content',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': title,
        })
        assert status == 200
        matching = [a for a in body['articles'] if a['id'] == article_id]
        # Should appear exactly once (latest version only)
        assert len(matching) == 1

    def test_list_articles_strips_content(self, api, l2_token, l1_token):
        title = unique_title('list-no-content')
        api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'Should not appear in list.',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': title,
        })
        assert status == 200
        for article in body['articles']:
            assert 'content' not in article

    def test_list_default_limit(self, api, l1_token):
        status, body = api.get('/kb', token=l1_token)
        assert status == 200
        assert isinstance(body['articles'], list)
        assert len(body['articles']) <= 25


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestKBUpdate:
    """PUT /kb/{id} creates new versions."""

    def test_update_creates_new_version(self, api, l2_token):
        title = unique_title('update-version')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'original',
        })
        article_id = created['article']['id']

        status, body = api.put(f'/kb/{article_id}', token=l2_token, body={
            'content': 'updated content',
        })
        assert status == 200
        assert body['article']['version'] == 2
        assert body['article']['content'] == 'updated content'

    def test_update_preserves_original_version(self, api, l2_token, l1_token):
        title = unique_title('update-preserve')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'original content',
        })
        article_id = created['article']['id']

        api.put(f'/kb/{article_id}', token=l2_token, body={
            'content': 'new content',
        })

        # Original version still accessible
        status, body = api.get(
            f'/kb/{article_id}/versions/1', token=l1_token,
        )
        assert status == 200
        assert body['article']['content'] == 'original content'

    def test_update_partial_fields(self, api, l2_token):
        title = unique_title('update-partial')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title,
            'service': 'original-service',
            'owner': 'Original Owner',
            'content': 'original',
        })
        article_id = created['article']['id']

        # Only update title
        status, body = api.put(f'/kb/{article_id}', token=l2_token, body={
            'title': f'{title}-updated',
        })
        assert status == 200
        # Service and owner should be preserved from v1
        assert body['article']['service'] == 'original-service'
        assert body['article']['owner'] == 'Original Owner'

    def test_update_nonexistent_returns_404(self, api, l2_token):
        status, _ = api.put('/kb/inttest-no-such-article-xyz', token=l2_token, body={
            'content': 'nope',
        })
        assert status == 404


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

class TestKBVersions:
    """Version history endpoints."""

    def test_get_versions_returns_all(self, api, l2_token, l1_token):
        title = unique_title('versions-all')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'v1',
        })
        article_id = created['article']['id']

        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'v2'})
        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'v3'})

        status, body = api.get(f'/kb/{article_id}/versions', token=l1_token)
        assert status == 200
        assert len(body['versions']) == 3

    def test_versions_strip_content(self, api, l2_token, l1_token):
        title = unique_title('versions-no-content')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'should not appear',
        })
        article_id = created['article']['id']

        status, body = api.get(f'/kb/{article_id}/versions', token=l1_token)
        assert status == 200
        for v in body['versions']:
            assert 'content' not in v

    def test_get_specific_version(self, api, l2_token, l1_token):
        title = unique_title('versions-specific')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'version one content',
        })
        article_id = created['article']['id']

        api.put(f'/kb/{article_id}', token=l2_token, body={
            'content': 'version two content',
        })

        status, body = api.get(f'/kb/{article_id}/versions/1', token=l1_token)
        assert status == 200
        assert body['article']['version'] == 1
        assert body['article']['content'] == 'version one content'


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestKBDelete:
    """DELETE /kb/{id} removes all versions."""

    def test_delete_removes_all_versions(self, api, l2_token, l3_token, l1_token):
        title = unique_title('delete-all')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'v1',
        })
        article_id = created['article']['id']

        # Create v2
        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'v2'})

        # Delete (L3 only)
        status, _ = api.delete(f'/kb/{article_id}', token=l3_token)
        assert status == 200

        # Verify gone
        status, _ = api.get(f'/kb/{article_id}', token=l1_token)
        assert status == 404

    def test_delete_nonexistent_returns_404(self, api, l3_token):
        status, _ = api.delete('/kb/inttest-no-such-article-xyz', token=l3_token)
        assert status == 404


# ---------------------------------------------------------------------------
# Search and filters
# ---------------------------------------------------------------------------

class TestKBSearch:
    """Search and filter operations on KB articles."""

    def test_search_by_title(self, api, l2_token, l1_token):
        keyword = f'uniqueword{int(time.time())}'
        title = unique_title(keyword)
        api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'searchable',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': keyword,
        })
        assert status == 200
        assert any(keyword in a['title'] for a in body['articles'])

    def test_search_case_insensitive(self, api, l2_token, l1_token):
        keyword = f'CaseTest{int(time.time())}'
        title = unique_title(keyword)
        api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'case test',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': keyword.upper(),
        })
        assert status == 200
        ids = [a['id'] for a in body['articles']]
        assert any(keyword.lower() in aid for aid in ids)

    def test_search_by_service(self, api, l2_token, l1_token):
        svc_name = f'svc-{int(time.time())}'
        title = unique_title('search-service')
        api.post('/kb', token=l2_token, body={
            'title': title, 'service': svc_name, 'content': 'service test',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': svc_name,
        })
        assert status == 200
        assert len(body['articles']) >= 1

    def test_filter_by_service(self, api, l2_token, l1_token):
        svc_name = f'filter-svc-{int(time.time())}'
        title = unique_title('filter-service')
        api.post('/kb', token=l2_token, body={
            'title': title, 'service': svc_name, 'content': 'filter test',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'service': svc_name,
        })
        assert status == 200
        for article in body['articles']:
            assert article['service'] == svc_name

    def test_filter_by_category(self, api, l2_token, l1_token):
        title = unique_title('filter-category')
        api.post('/kb', token=l2_token, body={
            'title': title, 'category': 'Security', 'content': 'category test',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'category': 'Security',
            'search': title,
        })
        assert status == 200
        for article in body['articles']:
            assert article['category'] == 'Security'

    def test_search_and_category_combined(self, api, l2_token, l1_token):
        keyword = f'combo{int(time.time())}'
        title = unique_title(keyword)
        api.post('/kb', token=l2_token, body={
            'title': title, 'category': 'Infrastructure',
            'content': 'combo test',
        })

        status, body = api.get('/kb', token=l1_token, params={
            'search': keyword,
            'category': 'Infrastructure',
        })
        assert status == 200
        assert len(body['articles']) >= 1

    def test_search_no_results(self, api, l1_token):
        status, body = api.get('/kb', token=l1_token, params={
            'search': 'zzzznonexistent-article-xyz-99999',
        })
        assert status == 200
        assert len(body['articles']) == 0


# ---------------------------------------------------------------------------
# Audit trail for KB operations
# ---------------------------------------------------------------------------

class TestKBAuditTrail:
    """KB operations create audit entries."""

    def test_create_logs_kb_create_audit(self, api, l2_token):
        title = unique_title('audit-create')
        api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'audit test',
        })

        status, audit = api.get('/actions/audit', token=l2_token, params={
            'action': 'kb-create',
        })
        assert status == 200
        assert len(audit['entries']) > 0

    def test_update_logs_kb_update_audit(self, api, l2_token):
        title = unique_title('audit-update')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'v1',
        })
        article_id = created['article']['id']
        api.put(f'/kb/{article_id}', token=l2_token, body={'content': 'v2'})

        status, audit = api.get('/actions/audit', token=l2_token, params={
            'action': 'kb-update',
        })
        assert status == 200
        assert len(audit['entries']) > 0

    def test_delete_logs_kb_delete_audit(self, api, l2_token, l3_token):
        title = unique_title('audit-delete')
        _, created = api.post('/kb', token=l2_token, body={
            'title': title, 'content': 'to delete',
        })
        article_id = created['article']['id']
        api.delete(f'/kb/{article_id}', token=l3_token)

        status, audit = api.get('/actions/audit', token=l3_token, params={
            'action': 'kb-delete',
        })
        assert status == 200
        assert len(audit['entries']) > 0
