output "lambda_log_group_name" {
  description = "Name of the CloudWatch log group for Lambda function logs."
  value       = aws_cloudwatch_log_group.lambda.name
}
