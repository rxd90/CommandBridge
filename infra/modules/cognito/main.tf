variable "project_name" { type = string }
variable "environment" { type = string }
variable "callback_urls" { type = list(string) }
variable "logout_urls" { type = list(string) }

resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  tags = {
    Name    = "CommandBridge User Pool"
    Purpose = "CommandBridge RBAC authentication"
  }
}

# RBAC Groups - admin-only, appear in cognito:groups JWT claim
resource "aws_cognito_user_group" "l1_operator" {
  name         = "L1-operator"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "L1 Support - pre-approved safe operations, can request high-risk"
  precedence   = 30
}

resource "aws_cognito_user_group" "l2_engineer" {
  name         = "L2-engineer"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "L2 Engineering - full operational access, can approve L1 requests"
  precedence   = 20
}

resource "aws_cognito_user_group" "l3_admin" {
  name         = "L3-admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "L3 Platform - unrestricted, manages portal config"
  precedence   = 10
}

resource "aws_cognito_user_pool_client" "portal" {
  name         = "${var.project_name}-portal"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret = false # Public client (SPA)

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
}

output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.main.arn
}

output "client_id" {
  value = aws_cognito_user_pool_client.portal.id
}

output "domain" {
  value = "${aws_cognito_user_pool_domain.main.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}

data "aws_region" "current" {}
