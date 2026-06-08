locals {
  bucket_name         = "llms-txt-crawler-output"
  jobs_table_name     = "llms-txt-jobs"
  sites_table_name    = "llms-txt-sites"
  ecr_repository_name = "llms-txt-agents"
  cluster_name        = "llms-txt-cluster"
  task_family         = "llms-txt-agent"
  ecs_log_group_name  = "/ecs/llms-txt"
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = local.bucket_name
}

module "dynamodb" {
  source           = "./modules/dynamodb"
  jobs_table_name  = local.jobs_table_name
  sites_table_name = local.sites_table_name
}

module "ecs" {
  source = "./modules/ecs"

  iam_role_arn        = var.iam_role_arn
  ecr_repository_name = local.ecr_repository_name
  cluster_name        = local.cluster_name
  task_family         = local.task_family
  log_group_name      = local.ecs_log_group_name
  aws_region          = var.aws_region

  bucket_name      = local.bucket_name
  jobs_table_name  = local.jobs_table_name
  sites_table_name = local.sites_table_name
  pinecone_index   = var.pinecone_index

  vpc_id = var.vpc_id
}

resource "aws_sqs_queue" "recrawl_dlq" {
  name                      = "llms-txt-recrawl-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "recrawl" {
  name                       = "llms-txt-recrawl"
  visibility_timeout_seconds = 120 # must match Lambda timeout (120s) to prevent double-processing
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.recrawl_dlq.arn
    maxReceiveCount     = 3
  })
}

module "lambda" {
  source           = "./modules/lambda"
  iam_role_arn     = var.iam_role_arn
  lambda_zip_path  = var.lambda_zip_path
  bucket_name      = local.bucket_name
  table_name       = local.jobs_table_name
  sites_table_name = local.sites_table_name
  pinecone_index   = var.pinecone_index

  ecs_cluster         = module.ecs.cluster_name
  ecs_task_definition = module.ecs.task_definition_arn
  ecs_security_group  = module.ecs.security_group_id
  ecs_subnet_ids      = var.subnet_ids

  recrawl_queue_url = aws_sqs_queue.recrawl.url
}

module "api_gateway" {
  source               = "./modules/api_gateway"
  lambda_invoke_arn    = module.lambda.invoke_arn
  lambda_function_name = module.lambda.function_name
}

module "observability" {
  source               = "./modules/observability"
  lambda_function_name = module.lambda.function_name
  api_gateway_id       = module.api_gateway.api_id
  ecs_log_group_name   = local.ecs_log_group_name
}

module "cloudfront" {
  source               = "./modules/cloudfront"
  api_gateway_endpoint = module.api_gateway.api_url
  api_gateway_key      = module.api_gateway.api_key
  basic_auth_user      = var.basic_auth_user
  basic_auth_password  = var.basic_auth_password
}

resource "aws_lambda_event_source_mapping" "recrawl_sqs" {
  event_source_arn = aws_sqs_queue.recrawl.arn
  function_name    = module.lambda.function_arn
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
  arn       = module.lambda.function_arn
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_recrawl.arn
}
