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
