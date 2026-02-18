"""Shared DynamoDB pagination and serialization helpers."""

import base64
import json
from decimal import Decimal


def decimal_to_native(obj):
    """Convert DynamoDB Decimal types to int/float for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    return obj


def decimal_to_int(obj):
    """Convert DynamoDB Decimal types to int for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_int(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_int(i) for i in obj]
    return obj


def encode_cursor(last_key):
    """Encode DynamoDB LastEvaluatedKey as a URL-safe base64 cursor."""
    if not last_key:
        return None
    return base64.urlsafe_b64encode(json.dumps(last_key, default=str).encode()).decode()


def decode_cursor(cursor):
    """Decode a base64 cursor back to DynamoDB ExclusiveStartKey."""
    if not cursor:
        return None
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor).decode())
        # Restore numeric types lost by json.dumps(default=str)
        if 'timestamp' in key and isinstance(key['timestamp'], str):
            key['timestamp'] = int(key['timestamp'])
        return key
    except Exception:
        return None
