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

output "anthropic_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the Anthropic API key."
  value       = module.secrets.anthropic_secret_arn
}
