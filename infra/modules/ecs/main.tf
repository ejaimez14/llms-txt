locals {
  base_environment = [
    { name = "TABLE",              value = var.jobs_table_name },
    { name = "SITES_TABLE",        value = var.sites_table_name },
    { name = "BUCKET",             value = var.bucket_name },
    { name = "PINECONE_INDEX",     value = var.pinecone_index },
    { name = "AWS_DEFAULT_REGION", value = var.aws_region },
  ]

  base_secrets = [
    { name = "ANTHROPIC_API_KEY", valueFrom = var.anthropic_secret_arn },
    { name = "PINECONE_API_KEY",  valueFrom = var.pinecone_secret_arn },
  ]
}

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

resource "aws_ecs_task_definition" "implementer" {
  family                   = var.implementer_task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([{
    name    = "implementer"
    image   = "${aws_ecr_repository.agents.repository_url}:latest"
    command = ["python", "-m", "src.tasks.implementer"]

    environment = local.base_environment

    secrets = concat(local.base_secrets, [
      { name = "GITHUB_TOKEN", valueFrom = var.github_secret_arn },
    ])

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "implementer"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "crawler" {
  family                   = var.crawler_task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([{
    name    = "crawler"
    image   = "${aws_ecr_repository.agents.repository_url}:latest"
    command = ["python", "-m", "src.tasks.crawler"]

    environment = local.base_environment
    secrets     = local.base_secrets

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "crawler"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "ui_planner" {
  family                   = var.ui_planner_task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([{
    name    = "ui-planner"
    image   = "${aws_ecr_repository.agents.repository_url}:latest"
    command = ["python", "-m", "src.tasks.ui_planner"]

    environment = local.base_environment
    secrets     = local.base_secrets

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ui-planner"
      }
    }
  }])
}
