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
  description = "Base invoke URL for the HTTP API."
  value       = module.api_gateway.api_url
}

output "cloudfront_url" {
  description = "Public URL — share this with interviewers"
  value       = module.cloudfront.cloudfront_url
}

output "frontend_bucket_name" {
  description = "Upload index.html here after terraform apply"
  value       = module.cloudfront.frontend_bucket_name
}

output "cloudfront_distribution_id" {
  description = "Use this ID to invalidate the CloudFront cache after updating index.html"
  value       = module.cloudfront.cloudfront_distribution_id
}
