resource "aws_ecr_repository" "agents" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecs_cluster" "main" {
  name = var.cluster_name
}

resource "aws_security_group" "fargate_tasks" {
  name        = "${var.cluster_name}-fargate-tasks"
  description = "Outbound internet access for Fargate agent tasks"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "agent" {
  family                   = var.task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([{
    name  = "agent"
    image = "${aws_ecr_repository.agents.repository_url}:latest"

    environment = [
      { name = "TABLE",              value = var.jobs_table_name },
      { name = "SITES_TABLE",        value = var.sites_table_name },
      { name = "BUCKET",             value = var.bucket_name },
      { name = "PINECONE_INDEX",     value = var.pinecone_index },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    ]

    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = "${data.aws_secretsmanager_secret.anthropic.arn}:value::" },
      { name = "PINECONE_API_KEY",  valueFrom = "${data.aws_secretsmanager_secret.pinecone.arn}:value::" },
      { name = "GITHUB_TOKEN",      valueFrom = "${data.aws_secretsmanager_secret.github.arn}:value::" },
      { name = "OPENAI_API_KEY",    valueFrom = "${data.aws_secretsmanager_secret.openai.arn}:value::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "agent"
      }
    }
  }])
}

# Omits ANTHROPIC_API_KEY so Claude Code CLI uses CLAUDE_CODE_OAUTH_TOKEN
resource "aws_ecs_task_definition" "implement" {
  family                   = var.implement_task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([{
    name  = "agent"
    image = "${aws_ecr_repository.agents.repository_url}:latest"

    environment = [
      { name = "TABLE",              value = var.jobs_table_name },
      { name = "SITES_TABLE",        value = var.sites_table_name },
      { name = "BUCKET",             value = var.bucket_name },
      { name = "PINECONE_INDEX",     value = var.pinecone_index },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
      { name = "FRONTEND_BUCKET",    value = var.frontend_bucket_name },
      { name = "CLOUDFRONT_URL",     value = var.cloudfront_url },
    ]

    secrets = [
      { name = "CLAUDE_CODE_OAUTH_TOKEN", valueFrom = "${data.aws_secretsmanager_secret.claude_code_token.arn}:value::" },
      { name = "PINECONE_API_KEY",        valueFrom = "${data.aws_secretsmanager_secret.pinecone.arn}:value::" },
      { name = "GITHUB_TOKEN",            valueFrom = "${data.aws_secretsmanager_secret.github.arn}:value::" },
      { name = "OPENAI_API_KEY",          valueFrom = "${data.aws_secretsmanager_secret.openai.arn}:value::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "implement"
      }
    }
  }])
}
