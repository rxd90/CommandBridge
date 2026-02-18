terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "commandbridge.state"
    key            = "infra/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "commandbridge.lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "CommandBridge"
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "CommandBridge"
      Team        = "ScotGov-Digital-Identity"
    }
  }
}

module "cognito" {
  source        = "./modules/cognito"
  project_name  = var.project_name
  environment   = var.environment
  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls
}

module "storage" {
  source       = "./modules/storage"
  project_name = var.project_name
  environment  = var.environment
}

module "lambdas" {
  source                = "./modules/lambdas"
  project_name          = var.project_name
  environment           = var.environment
  audit_table_name      = module.storage.audit_table_name
  audit_table_arn       = module.storage.audit_table_arn
  kb_table_name         = module.storage.kb_table_name
  kb_table_arn          = module.storage.kb_table_arn
  users_table_name      = module.storage.users_table_name
  users_table_arn       = module.storage.users_table_arn
  activity_table_name   = module.storage.activity_table_name
  activity_table_arn    = module.storage.activity_table_arn
  cognito_user_pool_id  = module.cognito.user_pool_id
  cognito_user_pool_arn = module.cognito.user_pool_arn
}

module "api" {
  source               = "./modules/api"
  project_name         = var.project_name
  environment          = var.environment
  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_client_id    = module.cognito.client_id
  lambda_invoke_arn    = module.lambdas.function_invoke_arn
  lambda_function_name = module.lambdas.function_name
  aws_region           = var.aws_region
}

module "hosting" {
  source       = "./modules/hosting"
  project_name = var.project_name
  environment  = var.environment
  domain_name  = var.domain_name
}
