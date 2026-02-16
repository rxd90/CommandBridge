"""Failover DNS to a secondary region via Route 53 health check override."""

import boto3


def execute(body: dict) -> dict:
    """Override a Route 53 health check to trigger regional failover."""
    health_check_id = body["target"]
    failover = body.get("failover", True)
    reason = body.get("reason", "Manual failover via CommandBridge")

    route53 = boto3.client("route53")

    route53.update_health_check(
        HealthCheckId=health_check_id,
        Inverted=failover,
    )

    hc = route53.get_health_check(HealthCheckId=health_check_id)
    config = hc["HealthCheck"]["HealthCheckConfig"]

    return {
        "status": "success",
        "message": (
            f"Health check {health_check_id} "
            f"{'inverted (failover active)' if failover else 'restored (failover cleared)'}"
        ),
        "reason": reason,
        "health_check_fqdn": config.get("FullyQualifiedDomainName"),
        "inverted": config.get("Inverted", False),
    }
