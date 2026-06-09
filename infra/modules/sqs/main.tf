resource "aws_sqs_queue" "recrawl_dlq" {
  name                      = "llms-txt-recrawl-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "recrawl" {
  name                       = "llms-txt-recrawl"
  # Must match Lambda timeout (120s) to prevent double-processing before visibility expires.
  visibility_timeout_seconds = 120
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.recrawl_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_lambda_event_source_mapping" "recrawl_sqs" {
  event_source_arn = aws_sqs_queue.recrawl.arn
  function_name    = var.lambda_function_arn
  batch_size       = 1
  enabled          = true
}

resource "aws_cloudwatch_event_rule" "daily_recrawl" {
  name                = "llms-txt-daily-recrawl"
  schedule_expression = "rate(1 day)"
  description         = "Triggers daily re-crawl of all indexed URLs"
}

resource "aws_cloudwatch_event_target" "daily_recrawl" {
  rule      = aws_cloudwatch_event_rule.daily_recrawl.name
  target_id = "LambdaRecrawlScheduler"
  arn       = var.lambda_function_arn
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_recrawl.arn
}
