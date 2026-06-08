output "function_name" {
  description = "Name of the Lambda function."
  value       = aws_lambda_function.api.function_name
}

output "invoke_arn" {
  description = "Invoke ARN used by API Gateway to trigger the Lambda function."
  value       = aws_lambda_function.api.invoke_arn
}

output "function_arn" {
  description = "ARN of the Lambda function."
  value       = aws_lambda_function.api.arn
}
