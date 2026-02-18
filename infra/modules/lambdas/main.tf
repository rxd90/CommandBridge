variable "project_name" { type = string }
variable "environment" { type = string }
variable "audit_table_name" { type = string }
variable "audit_table_arn" { type = string }
variable "kb_table_name" { type = string }
variable "kb_table_arn" { type = string }
variable "users_table_name" { type = string }
variable "users_table_arn" { type = string }
variable "activity_table_name" { type = string }
variable "activity_table_arn" { type = string }
variable "cognito_user_pool_id" { type = string }
variable "cognito_user_pool_arn" { type = string }

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-${var.environment}-actions-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json

  tags = {
    Name    = "CommandBridge Lambda Role"
    Purpose = "CommandBridge actions execution role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Scoped permissions for operational actions
data "aws_iam_policy_document" "actions" {
  # DynamoDB audit table
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [var.audit_table_arn, "${var.audit_table_arn}/index/*"]
  }

  # DynamoDB KB table
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [var.kb_table_arn, "${var.kb_table_arn}/index/*"]
  }

  # CloudWatch Logs (pull-logs action)
  statement {
    actions = ["logs:FilterLogEvents", "logs:DescribeLogGroups"]
    resources = [
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:*",
      "arn:aws:logs:${local.region}:${local.account_id}:log-group:*:*",
    ]
  }

  # ElastiCache (purge-cache, flush-token-cache actions)
  statement {
    actions = ["elasticache:DescribeCacheClusters", "elasticache:ModifyReplicationGroup"]
    resources = [
      "arn:aws:elasticache:${local.region}:${local.account_id}:cluster:*",
      "arn:aws:elasticache:${local.region}:${local.account_id}:replicationgroup:*",
    ]
  }

  # SSM (restart-pods, purge-cache via RunCommand, toggle-idv-provider)
  statement {
    actions   = ["ssm:SendCommand", "ssm:GetCommandInvocation"]
    resources = ["arn:aws:ssm:${local.region}:${local.account_id}:*"]
  }
  statement {
    actions   = ["ssm:PutParameter"]
    resources = ["arn:aws:ssm:${local.region}:${local.account_id}:parameter/*"]
  }

  # ECS (scale-service action)
  statement {
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = ["arn:aws:ecs:${local.region}:${local.account_id}:service/*/*"]
  }

  # Route 53 (failover-region action)
  statement {
    actions   = ["route53:UpdateHealthCheck", "route53:GetHealthCheck"]
    resources = ["arn:aws:route53:::healthcheck/*"]
  }

  # WAF (blacklist-ip action)
  statement {
    actions = ["wafv2:UpdateIPSet", "wafv2:GetIPSet"]
    resources = [
      "arn:aws:wafv2:${local.region}:${local.account_id}:regional/ipset/*/*",
      "arn:aws:wafv2:${local.region}:${local.account_id}:global/ipset/*/*",
    ]
  }

  # CloudFront (purge-cache action)
  statement {
    actions   = ["cloudfront:CreateInvalidation"]
    resources = ["arn:aws:cloudfront::${local.account_id}:distribution/*"]
  }

  # Secrets Manager (rotate-secrets action)
  statement {
    actions   = ["secretsmanager:RotateSecret", "secretsmanager:DescribeSecret"]
    resources = ["arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:*"]
  }

  # AppConfig (maintenance-mode, pause-enrolments actions)
  statement {
    actions = [
      "appconfig:StartDeployment",
      "appconfig:GetConfiguration",
      "appconfig:ListApplications",
      "appconfig:ListConfigurationProfiles",
      "appconfig:CreateHostedConfigurationVersion",
    ]
    resources = ["arn:aws:appconfig:${local.region}:${local.account_id}:*"]
  }

  # ELB (drain-traffic action)
  statement {
    actions   = ["elasticloadbalancing:DeregisterTargets", "elasticloadbalancing:DescribeTargetGroups"]
    resources = ["arn:aws:elasticloadbalancing:${local.region}:${local.account_id}:targetgroup/*/*"]
  }

  # DynamoDB users table (RBAC authorization)
  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"]
    resources = [var.users_table_arn]
  }

  # DynamoDB activity table (user interaction tracking)
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:BatchWriteItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [var.activity_table_arn, "${var.activity_table_arn}/index/*"]
  }

  # S3 (export-audit-log action)
  statement {
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.project_name}.site/audit-exports/*"]
  }

  # Cognito (disable-user, revoke-sessions, enable-user executors + admin user creation + role changes)
  statement {
    actions = [
      "cognito-idp:AdminDisableUser",
      "cognito-idp:AdminEnableUser",
      "cognito-idp:AdminUserGlobalSignOut",
      "cognito-idp:AdminCreateUser",
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminRemoveUserFromGroup",
      "cognito-idp:AdminDeleteUser"
    ]
    resources = [var.cognito_user_pool_arn]
  }
}

resource "aws_iam_role_policy" "actions" {
  name   = "${var.project_name}-actions-permissions"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.actions.json
}

resource "aws_lambda_function" "actions" {
  function_name = "${var.project_name}-${var.environment}-actions"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256

  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      AUDIT_TABLE    = var.audit_table_name
      KB_TABLE       = var.kb_table_name
      USERS_TABLE    = var.users_table_name
      ACTIVITY_TABLE = var.activity_table_name
      USER_POOL_ID   = var.cognito_user_pool_id
      ENVIRONMENT    = var.environment
    }
  }

  tags = {
    Name    = "CommandBridge Actions"
    Purpose = "CommandBridge operational action executor"
  }
}

output "function_invoke_arn" {
  value = aws_lambda_function.actions.invoke_arn
}

output "function_name" {
  value = aws_lambda_function.actions.function_name
}
