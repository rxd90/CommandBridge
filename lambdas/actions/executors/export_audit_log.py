"""Export audit log records to S3."""

import json
import time
from datetime import datetime, timezone

import boto3


def execute(body: dict) -> dict:
    """Scan DynamoDB audit table for a date range and write results to S3."""
    table_name = body.get("target", "commandbridge-dev-audit")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    bucket = body.get("bucket", "commandbridge.site")

    dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
    table = dynamodb.Table(table_name)

    scan_kwargs = {}
    if start_date and end_date:
        scan_kwargs["FilterExpression"] = (
            boto3.dynamodb.conditions.Attr("timestamp").between(start_date, end_date)
        )

    items = []
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"audit-exports/audit-{timestamp}.json"

    s3 = boto3.client("s3", region_name="eu-west-2")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(items, default=str),
        ContentType="application/json",
    )

    return {
        "status": "success",
        "message": f"Exported {len(items)} audit records to s3://{bucket}/{key}",
        "record_count": len(items),
        "s3_key": key,
    }
