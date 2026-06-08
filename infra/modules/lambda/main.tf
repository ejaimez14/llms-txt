data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "crawler_lambda" {
  name               = "crawler-agent-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "crawler_lambda_permissions" {
  statement {
    sid     = "S3ResultsAccess"
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:GetObject"]
    resources = [
      "${var.bucket_arn}/*",
    ]
  }

  statement {
    sid    = "DynamoDBJobsAccess"
    effect = "Allow"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:UpdateItem",
      "dynamodb:Scan",
    ]
    resources = [
      var.table_arn,
      "${var.table_arn}/index/*",
      var.sites_table_arn,
    ]
  }

  statement {
    sid     = "BedrockEmbeddings"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1",
    ]
  }

  statement {
    sid       = "AnthropicSecretAccess"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.anthropic_secret_arn]
  }
}

resource "aws_iam_role_policy" "crawler_lambda_permissions" {
  name   = "crawler-agent-permissions"
  role   = aws_iam_role.crawler_lambda.id
  policy = data.aws_iam_policy_document.crawler_lambda_permissions.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.crawler_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "crawler_agent" {
  function_name = "crawler-agent"
  filename      = var.lambda_zip_path
  role          = aws_iam_role.crawler_lambda.arn
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
      PINECONE_API_KEY                = var.pinecone_api_key
      PINECONE_INDEX                  = var.pinecone_index
      ECS_CLUSTER                     = var.ecs_cluster
      ECS_IMPLEMENTER_TASK_DEFINITION = var.ecs_implementer_task_definition
      ECS_CRAWLER_TASK_DEFINITION     = var.ecs_crawler_task_definition
      ECS_UI_PLANNER_TASK_DEFINITION  = var.ecs_ui_planner_task_definition
      ECS_SECURITY_GROUP              = var.ecs_security_group
      ECS_SUBNET_IDS                  = var.ecs_subnet_ids
    }
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_basic_execution]
}
