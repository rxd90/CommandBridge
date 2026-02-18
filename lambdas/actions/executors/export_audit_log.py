"""Export audit log records to S3."""

import json
import os
import re
from datetime import datetime, timezone

import boto3

# Table name must match expected pattern
_TABLE_NAME_RE = re.compile(r'^commandbridge-[\w-]+-audit$')

# Maximum records cap
_MAX_RECORDS_CAP = 50000


def execute(body: dict) -> dict:
    """Scan DynamoDB audit table for a date range and write results to S3."""
    table_name = os.environ.get("AUDIT_TABLE", body.get("target", "commandbridge-dev-audit"))
    if not _TABLE_NAME_RE.match(table_name):
        return {"status": "error", "message": f"Invalid audit table name: {table_name}. Must match commandbridge-*-audit."}

    start_date = body.get("start_date")
    end_date = body.get("end_date")
    bucket = body.get("bucket", "commandbridge.site")

    # Validate bucket name (basic S3 bucket naming rules)
    if not re.match(r'^[a-z0-9][a-z0-9.\-]+[a-z0-9]$', bucket):
        return {"status": "error", "message": "Invalid S3 bucket name."}

    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    table = dynamodb.Table(table_name)

    scan_kwargs = {}
    if start_date and end_date:
        scan_kwargs["FilterExpression"] = (
            boto3.dynamodb.conditions.Attr("timestamp").between(start_date, end_date)
        )

    try:
        max_records = min(int(body.get("max_records", 10000)), _MAX_RECORDS_CAP)
    except (ValueError, TypeError):
        max_records = 10000
    if max_records < 1:
        max_records = 1

    items = []
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response and len(items) < max_records:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    truncated = len(items) > max_records
    items = items[:max_records]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"audit-exports/audit-{timestamp}.json"

    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(items, default=str),
        ContentType="application/json",
    )

    result = {
        "status": "success",
        "message": f"Exported {len(items)} audit records to s3://{bucket}/{key}",
        "record_count": len(items),
        "s3_key": key,
    }
    if truncated:
        result["truncated"] = True
        result["message"] += f" (capped at {max_records} records)"
    return result
