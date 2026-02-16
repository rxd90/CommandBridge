variable "project_name" { type = string }
variable "environment" { type = string }
variable "audit_table_name" { type = string }
variable "audit_table_arn" { type = string }
variable "kb_table_name" { type = string }
variable "kb_table_arn" { type = string }

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
    actions   = ["logs:FilterLogEvents", "logs:DescribeLogGroups"]
    resources = ["*"]
  }

  # ElastiCache (purge-cache action)
  statement {
    actions   = ["elasticache:DescribeCacheClusters"]
    resources = ["*"]
  }

  # SSM (restart-pods, purge-cache via RunCommand)
  statement {
    actions   = ["ssm:SendCommand", "ssm:GetCommandInvocation"]
    resources = ["*"]
  }

  # ECS (scale-service action)
  statement {
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = ["*"]
  }

  # Route 53 (failover-region action)
  statement {
    actions   = ["route53:UpdateHealthCheck", "route53:GetHealthCheck"]
    resources = ["*"]
  }

  # WAF (blacklist-ip action)
  statement {
    actions   = ["wafv2:UpdateIPSet", "wafv2:GetIPSet"]
    resources = ["*"]
  }

  # CloudFront (purge-cache action)
  statement {
    actions   = ["cloudfront:CreateInvalidation"]
    resources = ["*"]
  }

  # Secrets Manager (rotate-secrets action)
  statement {
    actions   = ["secretsmanager:RotateSecret", "secretsmanager:DescribeSecret"]
    resources = ["*"]
  }

  # AppConfig (maintenance-mode, pause-enrolments actions)
  statement {
    actions   = ["appconfig:StartDeployment", "appconfig:GetConfiguration"]
    resources = ["*"]
  }

  # ELB (drain-traffic action)
  statement {
    actions   = ["elasticloadbalancing:DeregisterTargets", "elasticloadbalancing:DescribeTargetGroups"]
    resources = ["*"]
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
      AUDIT_TABLE = var.audit_table_name
      KB_TABLE    = var.kb_table_name
      ENVIRONMENT = var.environment
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
