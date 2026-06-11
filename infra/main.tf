locals {
  bucket_name           = "llms-txt-crawler-output"
  jobs_table_name       = "llms-txt-jobs"
  sites_table_name      = "llms-txt-sites"
  ecr_repository_name   = "llms-txt-agents"
  cluster_name          = "llms-txt-cluster"
  task_family           = "llms-txt-agent"
  implement_task_family = "llms-txt-implement"
  ecs_log_group_name    = "/ecs/llms-txt"
}

module "iam" {
  source     = "./modules/iam"
  aws_region = var.aws_region
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

  iam_role_arn        = module.iam.role_arn
  ecr_repository_name = local.ecr_repository_name
  cluster_name        = local.cluster_name
  task_family         = local.task_family
  log_group_name      = local.ecs_log_group_name
  aws_region          = var.aws_region

  bucket_name      = module.s3.bucket_name
  jobs_table_name  = local.jobs_table_name
  sites_table_name = local.sites_table_name
  pinecone_index   = var.pinecone_index

  vpc_id                = var.vpc_id
  implement_task_family = local.implement_task_family

  frontend_bucket_name = module.cloudfront.frontend_bucket_name
  cloudfront_url       = module.cloudfront.cloudfront_url
}

module "lambda" {
  source           = "./modules/lambda"
  iam_role_arn     = module.iam.role_arn
  lambda_zip_path  = var.lambda_zip_path
  bucket_name      = module.s3.bucket_name
  table_name       = local.jobs_table_name
  sites_table_name = local.sites_table_name
  pinecone_index   = var.pinecone_index

  ecs_cluster                   = module.ecs.cluster_name
  ecs_task_definition           = module.ecs.task_definition_arn
  ecs_implement_task_definition = module.ecs.implement_task_definition_arn
  ecs_security_group            = module.ecs.security_group_id
  ecs_subnet_ids                = var.subnet_ids

  recrawl_queue_url = module.sqs.queue_url
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

module "sqs" {
  source               = "./modules/sqs"
  lambda_function_arn  = module.lambda.function_arn
  lambda_function_name = module.lambda.function_name
}

module "cloudfront" {
  source               = "./modules/cloudfront"
  api_gateway_endpoint = module.api_gateway.api_url
  basic_auth_user      = var.basic_auth_user
  basic_auth_password  = var.basic_auth_password
}
