variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "commandbridge"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "domain_name" {
  description = "Custom domain for the portal (optional)"
  type        = string
  default     = ""
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs"
  type        = list(string)
  default = [
    "https://d2ej3zpo2eta45.cloudfront.net/callback",
    "http://localhost:5173/callback"
  ]
}

variable "logout_urls" {
  description = "Allowed OAuth logout URLs"
  type        = list(string)
  default = [
    "https://d2ej3zpo2eta45.cloudfront.net/login",
    "http://localhost:5173/login"
  ]
}
