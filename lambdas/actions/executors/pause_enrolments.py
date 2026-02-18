"""Pause or resume enrolments via AWS AppConfig feature flag."""

import json

import boto3


def execute(body: dict) -> dict:
    """Toggle the enrolments-paused feature flag in AppConfig."""
    environment = body.get("environment", "production")
    paused = body.get("paused", True)
    application = body.get("application", "CommandBridge")
    profile = body.get("profile", "feature-flags")

    appconfig = boto3.client("appconfig")

    apps = appconfig.list_applications()
    try:
        app_id = next(a["Id"] for a in apps["Items"] if a["Name"] == application)
    except StopIteration:
        return {"status": "error", "message": f"AppConfig application '{application}' not found"}

    profiles = appconfig.list_configuration_profiles(ApplicationId=app_id)
    try:
        profile_id = next(p["Id"] for p in profiles["Items"] if p["Name"] == profile)
    except StopIteration:
        return {"status": "error", "message": f"AppConfig profile '{profile}' not found"}

    config = {"enrolments_paused": {"enabled": paused}}
    appconfig.create_hosted_configuration_version(
        ApplicationId=app_id,
        ConfigurationProfileId=profile_id,
        Content=json.dumps(config).encode(),
        ContentType="application/json",
    )

    return {
        "status": "success",
        "message": f"Enrolments {'paused' if paused else 'resumed'} for {environment}",
        "enrolments_paused": paused,
    }
