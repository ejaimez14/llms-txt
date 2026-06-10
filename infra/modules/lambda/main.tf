resource "aws_lambda_function" "api" {
  function_name = "llms-txt-api"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  role             = var.iam_role_arn
  handler       = "src.handler.handler"
  runtime       = "python3.11"
  memory_size   = 1024
  timeout       = 120

  # Provides the localhost:2773 secrets cache that fetch_secret reads at runtime.
  layers = [var.secrets_extension_layer_arn]

  environment {
    variables = {
      BUCKET                          = var.bucket_name
      TABLE                           = var.table_name
      SITES_TABLE                     = var.sites_table_name
      PINECONE_INDEX                  = var.pinecone_index
      ECS_CLUSTER                   = var.ecs_cluster
      ECS_TASK_DEFINITION           = var.ecs_task_definition
      ECS_IMPLEMENT_TASK_DEFINITION = var.ecs_implement_task_definition
      ECS_SECURITY_GROUP            = var.ecs_security_group
      ECS_SUBNET_IDS                  = var.ecs_subnet_ids
      RECRAWL_QUEUE_URL               = var.recrawl_queue_url
    }
  }
}
