resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name              = "/aws/apigateway/llms-txt"
  retention_in_days = 14
}

resource "aws_apigatewayv2_api" "crawler" {
  name          = "llms-txt-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.crawler.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

locals {
  routes = [
    "POST /api/crawl",
    "GET /api/job",
    "GET /api/job/{id}/llms-txt",
    "GET /api/job/{id}/plan",
    "GET /api/jobs",
    "GET /api/site",
    "GET /api/search",
  ]
}

# REQUEST authorizer validates the x-api-key header; CloudFront injects the key
# as a custom origin header so the browser never holds it directly.
resource "aws_apigatewayv2_authorizer" "api_key" {
  api_id                            = aws_apigatewayv2_api.crawler.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = var.lambda_invoke_arn
  identity_sources                  = ["$request.header.x-api-key"]
  name                              = "api-key-authorizer"
  authorizer_payload_format_version = "2.0"
  enable_simple_responses           = true
}

resource "aws_apigatewayv2_route" "routes" {
  for_each = toset(local.routes)

  api_id             = aws_apigatewayv2_api.crawler.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.api_key.id
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.crawler.execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.crawler.id
  name        = "$default"
  auto_deploy = true

  # Stage-level throttling: 1 req/sec sustained, burst of 2
  default_route_settings {
    throttling_rate_limit  = 1
    throttling_burst_limit = 2
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn
    format = jsonencode({
      requestId = "$context.requestId"
      ip        = "$context.identity.sourceIp"
      method    = "$context.httpMethod"
      path      = "$context.path"
      status    = "$context.status"
      latency   = "$context.responseLatency"
      time      = "$context.requestTime"
    })
  }
}
