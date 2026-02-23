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

  # "2026-02" bucket written to every record; used for time-ordered listing
  # without a full-table scan. list_recent queries the current and previous month.
  attribute {
    name = "year_month"
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

  # Time-ordered listing without table scan; partition by calendar month
  global_secondary_index {
    name            = "time-index"
    hash_key        = "year_month"
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

  # Sparse index - only items with is_latest="true" appear
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

resource "aws_dynamodb_table" "users" {
  name         = "${var.project_name}-${var.environment}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name    = "CommandBridge Users"
    Purpose = "CommandBridge user roles and metadata"
  }
}

output "kb_table_name" {
  value = aws_dynamodb_table.kb.name
}

output "kb_table_arn" {
  value = aws_dynamodb_table.kb.arn
}

output "users_table_name" {
  value = aws_dynamodb_table.users.name
}

output "users_table_arn" {
  value = aws_dynamodb_table.users.arn
}

resource "aws_dynamodb_table" "activity" {
  name         = "${var.project_name}-${var.environment}-activity"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user"
  range_key    = "timestamp"

  attribute {
    name = "user"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "event_type"
    type = "S"
  }

  global_secondary_index {
    name            = "event-type-index"
    hash_key        = "event_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name    = "CommandBridge Activity Log"
    Purpose = "CommandBridge user interaction tracking with 90-day TTL"
  }
}

output "activity_table_name" {
  value = aws_dynamodb_table.activity.name
}

output "activity_table_arn" {
  value = aws_dynamodb_table.activity.arn
}
