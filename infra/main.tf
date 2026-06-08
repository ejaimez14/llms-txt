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
  task_family             = "llms-txt-agent"
  log_group_name          = "/ecs/llms-txt"
  aws_region              = var.aws_region

  bucket_name      = module.s3.bucket_name
  jobs_table_name  = module.dynamodb.jobs_table_name
  sites_table_name = module.dynamodb.sites_table_name
  pinecone_index   = var.pinecone_index

  vpc_id               = var.vpc_id
}

module "lambda" {
  source           = "./modules/lambda"
  iam_role_arn     = var.iam_role_arn
  lambda_zip_path  = var.lambda_zip_path
  bucket_name      = module.s3.bucket_name
  table_name       = module.dynamodb.jobs_table_name
  sites_table_name = module.dynamodb.sites_table_name
  pinecone_index   = var.pinecone_index

  ecs_cluster            = module.ecs.cluster_name
  ecs_task_definition    = module.ecs.task_definition_arn
  ecs_security_group     = module.ecs.security_group_id
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
