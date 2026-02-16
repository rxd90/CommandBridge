variable "project_name" { type = string }
variable "environment" { type = string }

resource "aws_dynamodb_table" "audit" {
  name         = "${var.project_name}-${var.environment}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  range_key    = "timestamp"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "user"
    type = "S"
  }

  attribute {
    name = "action"
    type = "S"
  }

  # Query by user: "show my actions"
  global_secondary_index {
    name            = "user-index"
    hash_key        = "user"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Query by action: "all cache purges"
  global_secondary_index {
    name            = "action-index"
    hash_key        = "action"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name    = "CommandBridge Audit Log"
    Purpose = "CommandBridge action audit trail"
  }
}

resource "aws_dynamodb_table" "kb" {
  name         = "${var.project_name}-${var.environment}-kb"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  range_key    = "version"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "version"
    type = "N"
  }

  attribute {
    name = "is_latest"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  attribute {
    name = "service"
    type = "S"
  }

  # Sparse index — only items with is_latest="true" appear
  global_secondary_index {
    name            = "latest-index"
    hash_key        = "is_latest"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  # Filter articles by service
  global_secondary_index {
    name            = "service-index"
    hash_key        = "service"
    range_key       = "updated_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name    = "CommandBridge Knowledge Base"
    Purpose = "CommandBridge KB articles with versioning"
  }
}

output "audit_table_name" {
  value = aws_dynamodb_table.audit.name
}

output "audit_table_arn" {
  value = aws_dynamodb_table.audit.arn
}

output "kb_table_name" {
  value = aws_dynamodb_table.kb.name
}

output "kb_table_arn" {
  value = aws_dynamodb_table.kb.arn
}
