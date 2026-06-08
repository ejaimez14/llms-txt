output "api_id" {
  description = "ID of the HTTP API, used by the observability module to configure dashboards."
  value       = aws_apigatewayv2_api.crawler.id
}

output "api_url" {
  description = "Base invoke URL for the deployed HTTP API stage."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_key" {
  description = "API key value that CloudFront injects as x-api-key; consumed by the cloudfront module."
  value       = random_password.api_key.result
  sensitive   = true
}

output "execution_arn" {
  description = "Execution ARN prefix for the API, used to scope Lambda invocation permissions."
  value       = aws_apigatewayv2_api.crawler.execution_arn
}
