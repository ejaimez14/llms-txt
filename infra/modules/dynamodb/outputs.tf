output "jobs_table_name" {
  description = "Name of the jobs DynamoDB table."
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_table_arn" {
  description = "ARN of the jobs DynamoDB table, used by IAM policies in later phases."
  value       = aws_dynamodb_table.jobs.arn
}

output "sites_table_name" {
  description = "Name of the sites DynamoDB table."
  value       = aws_dynamodb_table.sites.name
}

output "sites_table_arn" {
  description = "ARN of the sites DynamoDB table, used by IAM policies in later phases."
  value       = aws_dynamodb_table.sites.arn
}
