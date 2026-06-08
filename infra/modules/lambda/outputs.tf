output "function_name" {
  description = "Name of the Lambda function."
  value       = aws_lambda_function.crawler_agent.function_name
}

output "invoke_arn" {
  description = "Invoke ARN used by API Gateway to trigger the Lambda function."
  value       = aws_lambda_function.crawler_agent.invoke_arn
}

output "function_arn" {
  description = "ARN of the Lambda function."
  value       = aws_lambda_function.crawler_agent.arn
}
