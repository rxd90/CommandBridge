"""Load test for CommandBridge API using Locust.

Usage:
    pip install locust
    COMMANDBRIDGE_API_URL=https://xxx.execute-api.eu-west-2.amazonaws.com \
    AUTH_TOKEN=eyJraWQiO... \
    locust -f tests/load/locustfile.py

Open http://localhost:8089 in browser.
Set users (10-50), spawn rate (5/s), run for 5 minutes.
"""

import os

from locust import HttpUser, between, task


API_URL = os.environ.get('COMMANDBRIDGE_API_URL', 'http://localhost:8080')
AUTH_TOKEN = os.environ.get('AUTH_TOKEN', 'test-token')


class CommandBridgeUser(HttpUser):
    """Simulates an L1 operator using the CommandBridge portal."""

    host = API_URL
    wait_time = between(1, 5)

    def on_start(self):
        self.headers = {
            'Authorization': f'Bearer {AUTH_TOKEN}',
            'Content-Type': 'application/json',
        }

    @task(5)
    def get_permissions(self):
        """Dashboard load — most frequent action."""
        self.client.get('/actions/permissions', headers=self.headers)

    @task(2)
    def execute_pull_logs(self):
        """Execute a low-risk action."""
        self.client.post('/actions/execute', headers=self.headers, json={
            'action': 'pull-logs',
            'ticket': 'INC-LOAD-TEST',
            'reason': 'Load test — pull logs',
        })

    @task(2)
    def execute_purge_cache(self):
        """Execute a medium-risk action."""
        self.client.post('/actions/execute', headers=self.headers, json={
            'action': 'purge-cache',
            'ticket': 'INC-LOAD-TEST',
            'reason': 'Load test — purge cache',
        })

    @task(1)
    def request_maintenance_mode(self):
        """Request approval for a high-risk action."""
        self.client.post('/actions/request', headers=self.headers, json={
            'action': 'maintenance-mode',
            'ticket': 'CHG-LOAD-TEST',
            'reason': 'Load test — maintenance mode request',
        })

    @task(1)
    def get_audit(self):
        """View audit log."""
        self.client.get('/actions/audit', headers=self.headers)
