module "s3" {
  source      = "./modules/s3"
  bucket_name = "crawler-output"
}

module "dynamodb" {
  source           = "./modules/dynamodb"
  jobs_table_name  = "crawler-jobs"
  sites_table_name = "crawler-sites"
}

module "ecs" {
  source = "./modules/ecs"

  iam_role_arn            = var.iam_role_arn
  ecr_repository_name     = "llms-txt-agents"
  cluster_name            = "llms-txt-cluster"
  implementer_task_family = "llms-txt-implementer"
  crawler_task_family     = "llms-txt-crawler"
  ui_planner_task_family  = "llms-txt-ui-planner"
  log_group_name          = "/ecs/llms-txt"
  aws_region              = var.aws_region

  bucket_name      = module.s3.bucket_name
  jobs_table_name  = module.dynamodb.jobs_table_name
  sites_table_name = module.dynamodb.sites_table_name
  pinecone_index   = var.pinecone_index

  anthropic_secret_arn = var.anthropic_secret_arn
  github_secret_arn    = var.github_secret_arn
  pinecone_secret_arn  = var.pinecone_secret_arn
  vpc_id               = var.vpc_id
}

module "lambda" {
  source           = "./modules/lambda"
  iam_role_arn     = var.iam_role_arn
  lambda_zip_path  = var.lambda_zip_path
  bucket_name      = module.s3.bucket_name
  table_name       = module.dynamodb.jobs_table_name
  sites_table_name = module.dynamodb.sites_table_name
  pinecone_api_key = var.pinecone_api_key
  pinecone_index   = var.pinecone_index

  ecs_cluster                     = module.ecs.cluster_name
  ecs_implementer_task_definition = module.ecs.implementer_task_definition_arn
  ecs_crawler_task_definition     = module.ecs.crawler_task_definition_arn
  ecs_ui_planner_task_definition  = module.ecs.ui_planner_task_definition_arn
  ecs_security_group              = var.ecs_security_group
  ecs_subnet_ids                  = var.subnet_ids
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
  ecs_log_group_name   = "/ecs/llms-txt"
}
