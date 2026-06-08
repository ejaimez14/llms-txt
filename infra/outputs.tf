output "bucket_name" {
  description = "Name of the S3 bucket used to store crawler results."
  value       = module.s3.bucket_name
}

output "jobs_table_name" {
  description = "Name of the DynamoDB table storing crawl job history."
  value       = module.dynamodb.jobs_table_name
}

output "sites_table_name" {
  description = "Name of the DynamoDB table storing the latest state per URL."
  value       = module.dynamodb.sites_table_name
}

output "ecr_repository_url" {
  description = "Push agent Docker images here before running Fargate tasks"
  value       = module.ecs.ecr_repository_url
}

output "api_url" {
  description = "Base invoke URL for the HTTP API; consumed by the CloudFront module."
  value       = module.api_gateway.api_url
}

output "api_key" {
  description = "API key value injected by CloudFront as x-api-key; consumed by the cloudfront module."
  value       = module.api_gateway.api_key
  sensitive   = true
}
