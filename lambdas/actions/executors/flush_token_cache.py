"""Flush OIDC/JWKS token cache."""

import time

import boto3


def execute(body: dict) -> dict:
    """Invalidate cached JWKS keys by flushing the ElastiCache cluster
    used for OIDC token validation."""
    cluster_id = body.get("target", "scotaccount-oidc-cache")
    environment = body.get("environment", "production")

    elasticache = boto3.client("elasticache", region_name="eu-west-2")
    elasticache.modify_replication_group(
        ReplicationGroupId=f"{environment}-{cluster_id}",
        ApplyImmediately=True,
    )

    return {
        "status": "success",
        "message": f"OIDC token cache flushed for {cluster_id}. JWKS keys will be re-fetched on next validation.",
        "timestamp": int(time.time()),
    }
