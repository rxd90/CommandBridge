"""Toggle maintenance mode via AWS AppConfig feature flag."""

import json

import boto3


def execute(body: dict) -> dict:
    """Enable or disable maintenance mode by updating an AppConfig hosted configuration."""
    environment = body.get("environment", "production")
    enabled = body.get("enabled", True)
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

    config = {"maintenance_mode": {"enabled": enabled}}
    appconfig.create_hosted_configuration_version(
        ApplicationId=app_id,
        ConfigurationProfileId=profile_id,
        Content=json.dumps(config).encode(),
        ContentType="application/json",
    )

    return {
        "status": "success",
        "message": f"Maintenance mode {'enabled' if enabled else 'disabled'} for {environment}",
        "maintenance_mode": enabled,
    }
