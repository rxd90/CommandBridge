"""Executor unit tests with moto AWS mocking.

Tests all 10 executor modules in lambdas/actions/executors/.
"""

import json
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# pull_logs — CloudWatch Logs
# ---------------------------------------------------------------------------
@mock_aws
class TestPullLogsExecutor:
    def test_returns_events(self):
        client = boto3.client('logs', region_name='eu-west-2')
        client.create_log_group(logGroupName='/aws/production/my-service')
        client.create_log_stream(
            logGroupName='/aws/production/my-service',
            logStreamName='stream1',
        )
        client.put_log_events(
            logGroupName='/aws/production/my-service',
            logStreamName='stream1',
            logEvents=[{'timestamp': 1000000, 'message': 'test log line'}],
        )

        from actions.executors.pull_logs import execute
        result = execute({
            'target': 'my-service',
            'environment': 'production',
            'limit': 10,
        })
        assert result['status'] == 'success'
        assert 'events' in result

    def test_empty_log_group(self):
        client = boto3.client('logs', region_name='eu-west-2')
        client.create_log_group(logGroupName='/aws/production/empty-service')

        from actions.executors.pull_logs import execute
        result = execute({
            'target': 'empty-service',
            'environment': 'production',
        })
        assert result['status'] == 'success'


# ---------------------------------------------------------------------------
# blacklist_ip — WAFv2
# ---------------------------------------------------------------------------
@mock_aws
class TestBlacklistIpExecutor:
    def _create_ip_set(self):
        client = boto3.client('wafv2', region_name='eu-west-2')
        resp = client.create_ip_set(
            Name='blocked-ips',
            Scope='REGIONAL',
            IPAddressVersion='IPV4',
            Addresses=[],
        )
        return resp['Summary']['Id']

    def test_adds_ip_to_set(self):
        ip_set_id = self._create_ip_set()
        from actions.executors.blacklist_ip import execute
        result = execute({
            'target': '10.0.0.1',
            'ip_set_id': ip_set_id,
            'ip_set_name': 'blocked-ips',
            'scope': 'REGIONAL',
        })
        assert result['status'] == 'success'
        assert '10.0.0.1/32' in result['message']

    def test_duplicate_ip_returns_noop(self):
        client = boto3.client('wafv2', region_name='eu-west-2')
        resp = client.create_ip_set(
            Name='blocked-ips-dup',
            Scope='REGIONAL',
            IPAddressVersion='IPV4',
            Addresses=['10.0.0.1/32'],
        )
        ip_set_id = resp['Summary']['Id']
        from actions.executors.blacklist_ip import execute
        result = execute({
            'target': '10.0.0.1',
            'ip_set_id': ip_set_id,
            'ip_set_name': 'blocked-ips-dup',
            'scope': 'REGIONAL',
        })
        assert result['status'] == 'noop'


# ---------------------------------------------------------------------------
# rotate_secrets — Secrets Manager
# ---------------------------------------------------------------------------
@mock_aws
class TestRotateSecretsExecutor:
    def test_triggers_rotation(self):
        client = boto3.client('secretsmanager', region_name='eu-west-2')
        client.create_secret(Name='test-secret', SecretString='s3cr3t')

        from actions.executors.rotate_secrets import execute
        result = execute({'target': 'test-secret'})
        assert result['status'] == 'success'
        assert 'test-secret' in result['message']


# ---------------------------------------------------------------------------
# scale_service — ECS
# ---------------------------------------------------------------------------
@mock_aws
class TestScaleServiceExecutor:
    def test_scales_service(self):
        ecs = boto3.client('ecs', region_name='eu-west-2')
        ecs.create_cluster(clusterName='production')

        # Register a task definition first
        ecs.register_task_definition(
            family='web',
            containerDefinitions=[{
                'name': 'web',
                'image': 'nginx:latest',
                'memory': 256,
            }],
        )
        ecs.create_service(
            cluster='production',
            serviceName='web-service',
            taskDefinition='web',
            desiredCount=1,
        )

        from actions.executors.scale_service import execute
        result = execute({
            'target': 'web-service',
            'cluster': 'production',
            'desired_count': 3,
        })
        assert result['status'] == 'success'
        assert '3' in result['message']


# ---------------------------------------------------------------------------
# failover_region — Route 53
# ---------------------------------------------------------------------------
@mock_aws
class TestFailoverRegionExecutor:
    def test_inverts_health_check(self):
        route53 = boto3.client('route53', region_name='us-east-1')
        resp = route53.create_health_check(
            CallerReference='test-hc-1',
            HealthCheckConfig={
                'FullyQualifiedDomainName': 'api.scotaccount.gov.uk',
                'Port': 443,
                'Type': 'HTTPS',
                'RequestInterval': 30,
                'FailureThreshold': 3,
            },
        )
        hc_id = resp['HealthCheck']['Id']

        from actions.executors.failover_region import execute
        result = execute({
            'target': hc_id,
            'failover': True,
            'reason': 'Test failover',
        })
        assert result['status'] == 'success'
        assert 'failover active' in result['message']


# ---------------------------------------------------------------------------
# drain_traffic — ELBv2
# ---------------------------------------------------------------------------
class TestDrainTrafficExecutor:
    def test_deregisters_targets(self):
        """ELBv2 deregister + waiter is hard to mock fully; use unittest.mock."""
        with patch('boto3.client') as mock_client:
            mock_elbv2 = MagicMock()
            mock_client.return_value = mock_elbv2
            mock_elbv2.deregister_targets.return_value = {}
            mock_waiter = MagicMock()
            mock_elbv2.get_waiter.return_value = mock_waiter

            from actions.executors import drain_traffic
            import importlib
            importlib.reload(drain_traffic)
            result = drain_traffic.execute({
                'target': 'arn:aws:elasticloadbalancing:eu-west-2:123456789:targetgroup/test-tg/abc123',
                'instance_ids': ['i-1234567890abcdef0'],
                'port': 80,
            })
            assert result['status'] == 'success'
            mock_elbv2.deregister_targets.assert_called_once()
            mock_waiter.wait.assert_called_once()


# ---------------------------------------------------------------------------
# restart_pods — SSM
# ---------------------------------------------------------------------------
@mock_aws
class TestRestartPodsExecutor:
    def test_sends_kubectl_command(self):
        """SSM send_command requires managed instances which are hard to mock.
        Use unittest.mock instead."""
        with patch('boto3.client') as mock_client:
            mock_ssm = MagicMock()
            mock_client.return_value = mock_ssm
            mock_ssm.send_command.return_value = {
                'Command': {'CommandId': 'cmd-123', 'Status': 'Pending'}
            }

            from actions.executors import restart_pods
            import importlib
            importlib.reload(restart_pods)
            result = restart_pods.execute({
                'target': 'auth-service',
                'namespace': 'default',
                'environment': 'production',
                'instance_ids': ['i-abc123'],
            })
            assert result['status'] == 'success'
            assert 'auth-service' in result['message']


# ---------------------------------------------------------------------------
# purge_cache — ElastiCache + CloudFront
# ---------------------------------------------------------------------------
class TestPurgeCacheExecutor:
    def test_purges_cache(self):
        """ElastiCache replication group + CloudFront mocked together."""
        with patch('boto3.client') as mock_client:
            mock_ec = MagicMock()
            mock_cf = MagicMock()

            def client_factory(service, **kwargs):
                if service == 'elasticache':
                    return mock_ec
                elif service == 'cloudfront':
                    return mock_cf
                return MagicMock()

            mock_client.side_effect = client_factory
            mock_ec.modify_replication_group.return_value = {}
            mock_cf.create_invalidation.return_value = {
                'Invalidation': {'Id': 'inv-123', 'Status': 'InProgress'}
            }

            from actions.executors import purge_cache
            import importlib
            importlib.reload(purge_cache)
            result = purge_cache.execute({
                'target': 'redis-cluster-1',
                'distribution_id': 'E1234567890',
                'environment': 'production',
            })
            assert result['status'] == 'success'


# ---------------------------------------------------------------------------
# maintenance_mode — AppConfig (mocked, not supported by moto)
# ---------------------------------------------------------------------------
class TestMaintenanceModeExecutor:
    def test_enables_maintenance_mode(self):
        with patch('boto3.client') as mock_client:
            mock_appconfig = MagicMock()
            mock_client.return_value = mock_appconfig
            mock_appconfig.list_applications.return_value = {
                'Items': [{'Id': 'app-123', 'Name': 'CommandBridge'}]
            }
            mock_appconfig.list_configuration_profiles.return_value = {
                'Items': [{'Id': 'prof-123', 'Name': 'feature-flags'}]
            }
            mock_appconfig.create_hosted_configuration_version.return_value = {}

            from actions.executors import maintenance_mode
            import importlib
            importlib.reload(maintenance_mode)
            result = maintenance_mode.execute({
                'enabled': True,
                'environment': 'production',
            })
            assert result['status'] == 'success'
            assert result['maintenance_mode'] is True


# ---------------------------------------------------------------------------
# pause_enrolments — AppConfig (mocked)
# ---------------------------------------------------------------------------
class TestPauseEnrolmentsExecutor:
    def test_pauses_enrolments(self):
        with patch('boto3.client') as mock_client:
            mock_appconfig = MagicMock()
            mock_client.return_value = mock_appconfig
            mock_appconfig.list_applications.return_value = {
                'Items': [{'Id': 'app-123', 'Name': 'CommandBridge'}]
            }
            mock_appconfig.list_configuration_profiles.return_value = {
                'Items': [{'Id': 'prof-123', 'Name': 'feature-flags'}]
            }
            mock_appconfig.create_hosted_configuration_version.return_value = {}

            from actions.executors import pause_enrolments
            import importlib
            importlib.reload(pause_enrolments)
            result = pause_enrolments.execute({
                'paused': True,
                'environment': 'production',
            })
            assert result['status'] == 'success'
            assert result['enrolments_paused'] is True
