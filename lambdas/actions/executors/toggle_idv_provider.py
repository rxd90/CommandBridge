"""Toggle the active identity document verification provider."""

import os

import boto3

# Allowlist of known IDV provider identifiers.
# Update this set when onboarding or offboarding a provider.
_ALLOWED_PROVIDERS = {"yoti", "onfido", "passfort", "acuant", "gbg"}

# SSM parameter path is infrastructure config — not caller-controlled.
_PARAM_NAME = os.environ.get("IDV_PROVIDER_PARAM", "/scotaccount/idv/active-provider")


def execute(body: dict) -> dict:
    """Switch the active IDV provider by updating the SSM parameter
    that controls which verification backend is used."""
    target_provider = (body.get("target") or "").strip().lower()

    if not target_provider:
        return {"status": "error", "message": "target (provider name) is required."}

    if target_provider not in _ALLOWED_PROVIDERS:
        return {
            "status": "error",
            "message": "Unknown provider '{}'. Allowed values: {}.".format(
                target_provider, ", ".join(sorted(_ALLOWED_PROVIDERS))
            ),
        }

    ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    ssm.put_parameter(
        Name=_PARAM_NAME,
        Value=target_provider,
        Type="String",
        Overwrite=True,
    )

    return {
        "status": "success",
        "message": "IDV provider switched to {}".format(target_provider),
    }
