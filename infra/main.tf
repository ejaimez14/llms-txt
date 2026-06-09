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

  implementer_repo        = var.implementer_repo
  implementer_base_branch = var.implementer_base_branch
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
