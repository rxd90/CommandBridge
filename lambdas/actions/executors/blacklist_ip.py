"""Block an IP address by updating a WAF IP set."""

import ipaddress
import re

import boto3

_VALID_SCOPES = {"REGIONAL", "CLOUDFRONT"}
_IP_SET_ID_RE = re.compile(r'^[\da-f-]+$', re.IGNORECASE)


def _validate_cidr(value: str) -> str | None:
    """Validate and normalise an IP address or CIDR block. Returns the CIDR string or None."""
    try:
        if "/" not in value:
            addr = ipaddress.ip_address(value)
            suffix = 32 if addr.version == 4 else 128
            return f"{value}/{suffix}"
        network = ipaddress.ip_network(value, strict=False)
        return str(network)
    except ValueError:
        return None


def execute(body: dict) -> dict:
    """Add an IP address to a WAF IP set to block it."""
    ip_address = body.get("target", "")
    if not ip_address:
        return {"status": "error", "message": "target (IP address or CIDR) is required."}

    cidr = _validate_cidr(ip_address)
    if cidr is None:
        return {"status": "error", "message": f"Invalid IP address or CIDR: {ip_address}"}

    ip_set_name = body.get("ip_set_name", "blocked-ips")
    ip_set_id = body.get("ip_set_id", "")
    if not ip_set_id or not _IP_SET_ID_RE.match(ip_set_id):
        return {"status": "error", "message": "ip_set_id is required and must be a valid UUID."}

    scope = body.get("scope", "REGIONAL")
    if scope not in _VALID_SCOPES:
        return {"status": "error", "message": f"scope must be one of: {', '.join(sorted(_VALID_SCOPES))}"}

    waf = boto3.client("wafv2")

    ip_set = waf.get_ip_set(Name=ip_set_name, Scope=scope, Id=ip_set_id)
    current_addresses = ip_set["IPSet"]["Addresses"]
    lock_token = ip_set["LockToken"]

    if cidr in current_addresses:
        return {"status": "noop", "message": f"{cidr} is already blocked"}

    updated_addresses = current_addresses + [cidr]
    waf.update_ip_set(
        Name=ip_set_name,
        Scope=scope,
        Id=ip_set_id,
        Addresses=updated_addresses,
        LockToken=lock_token,
    )

    return {
        "status": "success",
        "message": f"Blocked {cidr} in WAF IP set {ip_set_name}",
        "total_blocked": len(updated_addresses),
    }
