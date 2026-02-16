"""Purge cache from ElastiCache and CloudFront."""

import time

import boto3


def execute(body: dict) -> dict:
    """Flush an ElastiCache replication group and create a CloudFront invalidation."""
    environment = body.get("environment", "production")
    cluster_id = body["target"]
    distribution_id = body.get("distribution_id")
    paths = body.get("paths", ["/*"])

    elasticache = boto3.client("elasticache")
    elasticache.modify_replication_group(
        ReplicationGroupId=f"{environment}-{cluster_id}",
        ApplyImmediately=True,
    )

    invalidation = None
    if distribution_id:
        cloudfront = boto3.client("cloudfront")
        invalidation = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(paths), "Items": paths},
                "CallerReference": f"purge-{int(time.time())}",
            },
        )

    return {
        "status": "success",
        "message": f"Cache purged for {cluster_id}" + (
            f" and CloudFront {distribution_id}" if distribution_id else ""
        ),
        "invalidation_id": (invalidation or {}).get("Invalidation", {}).get("Id"),
    }
