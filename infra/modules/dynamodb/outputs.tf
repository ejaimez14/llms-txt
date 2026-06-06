output "jobs_table_name" {
  description = "Name of the DynamoDB table storing crawl job history."
  value       = aws_dynamodb_table.crawl_jobs.name
}

output "jobs_table_arn" {
  description = "ARN of the crawl jobs table, used by Lambda IAM policy in Phase 5."
  value       = aws_dynamodb_table.crawl_jobs.arn
}

output "sites_table_name" {
  description = "Name of the DynamoDB table storing the latest crawl state per URL."
  value       = aws_dynamodb_table.crawled_sites.name
}

output "sites_table_arn" {
  description = "ARN of the crawled sites table, used by Lambda IAM policy in Phase 5."
  value       = aws_dynamodb_table.crawled_sites.arn
}
