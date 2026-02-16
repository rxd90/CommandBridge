"""Block an IP address by updating a WAF IP set."""

import boto3


def execute(body: dict) -> dict:
    """Add an IP address to a WAF IP set to block it."""
    ip_address = body["target"]
    ip_set_name = body.get("ip_set_name", "blocked-ips")
    ip_set_id = body["ip_set_id"]
    scope = body.get("scope", "REGIONAL")

    if "/" not in ip_address:
        ip_address = f"{ip_address}/32"

    waf = boto3.client("wafv2")

    ip_set = waf.get_ip_set(Name=ip_set_name, Scope=scope, Id=ip_set_id)
    current_addresses = ip_set["IPSet"]["Addresses"]
    lock_token = ip_set["LockToken"]

    if ip_address in current_addresses:
        return {"status": "noop", "message": f"{ip_address} is already blocked"}

    updated_addresses = current_addresses + [ip_address]
    waf.update_ip_set(
        Name=ip_set_name,
        Scope=scope,
        Id=ip_set_id,
        Addresses=updated_addresses,
        LockToken=lock_token,
    )

    return {
        "status": "success",
        "message": f"Blocked {ip_address} in WAF IP set {ip_set_name}",
        "total_blocked": len(updated_addresses),
    }
