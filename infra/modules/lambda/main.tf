resource "aws_lambda_function" "api" {
  function_name = "llms-txt-api"
  filename      = var.lambda_zip_path
  role          = var.iam_role_arn
  handler       = "src.handler.handler"
  runtime       = "python3.11"
  memory_size   = 1024
  timeout       = 120

  reserved_concurrent_executions = 5

  environment {
    variables = {
      BUCKET                          = var.bucket_name
      TABLE                           = var.table_name
      SITES_TABLE                     = var.sites_table_name
      PINECONE_INDEX                  = var.pinecone_index
      ECS_CLUSTER                     = var.ecs_cluster
      ECS_IMPLEMENTER_TASK_DEFINITION = var.ecs_implementer_task_definition
      ECS_CRAWLER_TASK_DEFINITION     = var.ecs_crawler_task_definition
      ECS_UI_PLANNER_TASK_DEFINITION  = var.ecs_ui_planner_task_definition
      ECS_SECURITY_GROUP              = var.ecs_security_group
      ECS_SUBNET_IDS                  = var.ecs_subnet_ids
    }
  }
}
