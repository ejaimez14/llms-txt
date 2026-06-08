resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_dashboard" "crawler" {
  dashboard_name = "crawler-agent"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Invocations"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name, { stat = "Sum" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Errors"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name, { stat = "Sum" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Duration"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "Average" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "p99" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "API Gateway 4xx / 5xx"
          view   = "timeSeries"
          region = "us-east-1"
          metrics = [
            ["AWS/ApiGateway", "4XXError", "ApiId", var.api_gateway_id, { stat = "Sum" }],
            ["AWS/ApiGateway", "5XXError", "ApiId", var.api_gateway_id, { stat = "Sum" }]
          ]
          period = 300
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "ecs_tasks" {
  name              = var.ecs_log_group_name
  retention_in_days = 14
}

