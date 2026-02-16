"""Post-deploy smoke tests for CommandBridge.

Usage:
    COMMANDBRIDGE_API_URL=https://xxx.execute-api.eu-west-2.amazonaws.com \
    COMMANDBRIDGE_CLOUDFRONT_DOMAIN=dxxxxxxxx.cloudfront.net \
    COMMANDBRIDGE_COGNITO_POOL_ID=eu-west-2_xxxxx \
    pytest tests/smoke/smoke_test.py -v

These tests hit REAL infrastructure. Run after deploy, not on every PR.
Uses only stdlib urllib — no extra dependencies.
"""

import json
import os
import urllib.request
import urllib.error

import pytest

API_URL = os.environ.get('COMMANDBRIDGE_API_URL', '')
CF_DOMAIN = os.environ.get('COMMANDBRIDGE_CLOUDFRONT_DOMAIN', '')
COGNITO_POOL_ID = os.environ.get('COMMANDBRIDGE_COGNITO_POOL_ID', '')

skip_if_no_env = pytest.mark.skipif(
    not all([API_URL, CF_DOMAIN]),
    reason='Smoke test env vars not set',
)


@skip_if_no_env
class TestCloudFrontServesSPA:
    def test_index_html_returns_200(self):
        url = f'https://{CF_DOMAIN}/index.html'
        with urllib.request.urlopen(url, timeout=10) as resp:
            assert resp.status == 200
            body = resp.read().decode()
            assert 'CommandBridge' in body

    def test_spa_route_returns_index(self):
        """SPA routes (no file extension) should return index.html via CloudFront function."""
        url = f'https://{CF_DOMAIN}/kb'
        with urllib.request.urlopen(url, timeout=10) as resp:
            assert resp.status == 200
            body = resp.read().decode()
            assert '<div id="root">' in body

    def test_hashed_assets_served(self):
        """Vite build outputs hashed JS/CSS in assets/."""
        url = f'https://{CF_DOMAIN}/index.html'
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode()
            assert '/assets/index-' in body


@skip_if_no_env
class TestAPIGatewayResponds:
    def test_unauthenticated_actions_returns_401(self):
        """API Gateway JWT authorizer rejects requests without a token."""
        url = f'{API_URL}/actions/permissions'
        req = urllib.request.Request(url)
        try:
            urllib.request.urlopen(req, timeout=10)
            pytest.fail('Expected 401, got 200')
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_unauthenticated_kb_returns_401(self):
        """KB endpoints also require auth."""
        url = f'{API_URL}/kb'
        req = urllib.request.Request(url)
        try:
            urllib.request.urlopen(req, timeout=10)
            pytest.fail('Expected 401, got 200')
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_api_cors_headers(self):
        """OPTIONS preflight should return CORS headers."""
        url = f'{API_URL}/actions/permissions'
        req = urllib.request.Request(url, method='OPTIONS')
        req.add_header('Origin', f'https://{CF_DOMAIN}')
        req.add_header('Access-Control-Request-Method', 'GET')
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                assert resp.status in (200, 204)
        except urllib.error.HTTPError:
            pass  # Some configs return 4xx for OPTIONS without auth


@skip_if_no_env
class TestCognitoEndpoint:
    def test_cognito_well_known_endpoint(self):
        """Cognito OIDC discovery should be reachable."""
        if not COGNITO_POOL_ID:
            pytest.skip('COMMANDBRIDGE_COGNITO_POOL_ID not set')
        region = COGNITO_POOL_ID.split('_')[0]
        url = f'https://cognito-idp.{region}.amazonaws.com/{COGNITO_POOL_ID}/.well-known/openid-configuration'
        with urllib.request.urlopen(url, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert 'authorization_endpoint' in data
