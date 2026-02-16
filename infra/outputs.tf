output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito App Client ID"
  value       = module.cognito.client_id
}

output "cognito_domain" {
  description = "Cognito hosted UI domain"
  value       = module.cognito.domain
}

output "api_gateway_url" {
  description = "API Gateway base URL"
  value       = module.api.api_url
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = module.hosting.cloudfront_domain
}

output "s3_bucket" {
  description = "S3 bucket for site hosting"
  value       = module.hosting.bucket_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidation"
  value       = module.hosting.distribution_id
}

output "audit_table_name" {
  description = "DynamoDB audit table name"
  value       = module.storage.audit_table_name
}

output "kb_table_name" {
  description = "DynamoDB KB table name"
  value       = module.storage.kb_table_name
}
