# --- Control-room Lambda route (/control/*) ---
# The org control-room Lambda is created by the agent-org-platform deploy; reference it by name and
# route /control/* to it through this shared HTTP API, behind the same x-api-key authorizer used by
# the main API (so direct API Gateway access without CloudFront's injected header is rejected).

data "aws_lambda_function" "control_room" {
  function_name = var.control_room_lambda_function_name
}

resource "aws_apigatewayv2_integration" "control_room" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = data.aws_lambda_function.control_room.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "control_room" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "ANY /control/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.control_room.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.api_key.id
}

resource "aws_lambda_permission" "control_room_apigw" {
  statement_id  = "AllowAPIGatewayInvokeControlRoom"
  action        = "lambda:InvokeFunction"
  function_name = data.aws_lambda_function.control_room.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
