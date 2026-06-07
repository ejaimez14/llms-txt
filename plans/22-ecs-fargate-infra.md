# Component: ECS Fargate Infrastructure (Plan 22)

## How to Use This Plan

You are implementing the Terraform infrastructure for the UI implementer agent (Plan 21).
This adds an `infra/modules/ecs/` module for the brand-new ECS resources, and extends the
existing `infra/modules/observability/` module with a CloudWatch log group for task logs.

The IAM role already exists outside of Terraform — it is passed as a variable and reused for
both the ECS task execution role and the task role. No IAM resources are created here.

Dependencies:
- [17-terraform-hosting.md](17-terraform-hosting.md) — lambda and observability modules must exist first
- [21-ui-implementer-agent.md](21-ui-implementer-agent.md) — the code this infrastructure runs

---

## Owner

Infra subagent

## Output Files

```
infra/
  main.tf                    ← extend (add ecs module)
  variables.tf               ← extend (add ecs variables)
  outputs.tf                 ← extend (add ecr_repository_url output)
  modules/
    ecs/
      main.tf                ← new
      variables.tf           ← new
      outputs.tf             ← new
    observability/
      main.tf                ← extend (add ECS log group)
      variables.tf           ← extend (add ecs_log_group_name variable)
```

---

## What Is Brand New vs. What Extends Existing

**New module — `infra/modules/ecs/`:**
- ECR repository (Docker image storage)
- ECS cluster
- ECS task definition (container config, env vars, secrets, log routing)
- Security group for Fargate tasks (outbound internet only)

**Extends existing — `infra/modules/observability/`:**
- CloudWatch log group for ECS task stdout/stderr

**Manual IAM addition (outside Terraform):**
The existing IAM role needs two additional permissions for the Lambda function to dispatch
Fargate tasks. Add these to the role policy outside of Terraform:
- `ecs:RunTask` scoped to the implementer task definition ARN
- `iam:PassRole` scoped to the same IAM role ARN (required by AWS when ECS assumes it)

---

## ECS Module — `infra/modules/ecs/`

### `modules/ecs/variables.tf`

```hcl
variable "iam_role_arn" {
  description = "ARN of the existing IAM role used for both task execution and task role"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository for the implementer Docker image"
}

variable "cluster_name" {
  description = "Name of the ECS cluster"
}

variable "task_family" {
  description = "ECS task definition family name"
}

variable "task_cpu" {
  description = "vCPU units for the Fargate task (1024 = 1 vCPU)"
  default     = 1024
}

variable "task_memory" {
  description = "Memory in MB for the Fargate task"
  default     = 2048
}

variable "container_name" {
  description = "Name of the container inside the task definition"
}

variable "log_group_name" {
  description = "CloudWatch log group name for task stdout/stderr"
}

variable "aws_region" {
  description = "AWS region for log configuration"
}

variable "bucket_name" {
  description = "S3 bucket name passed to the container as an environment variable"
}

variable "jobs_table_name" {
  description = "DynamoDB jobs table name"
}

variable "sites_table_name" {
  description = "DynamoDB sites table name"
}

variable "pinecone_index" {
  description = "Pinecone index name"
}

variable "anthropic_secret_arn" {
  description = "Secrets Manager ARN for the Anthropic API key"
}

variable "github_secret_arn" {
  description = "Secrets Manager ARN for the GitHub token"
}

variable "pinecone_secret_arn" {
  description = "Secrets Manager ARN for the Pinecone API key"
}

variable "vpc_id" {
  description = "VPC ID for the Fargate task security group"
}
```

### `modules/ecs/main.tf`

```hcl
resource "aws_ecr_repository" "implementer" {
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
  description = "Outbound internet access for Fargate implementer tasks"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "implementer" {
  family                   = var.task_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.iam_role_arn
  task_role_arn            = var.iam_role_arn

  container_definitions = jsonencode([
    {
      name    = var.container_name
      image   = "${aws_ecr_repository.implementer.repository_url}:latest"
      command = ["python", "-m", "src.tasks.implementer"]

      environment = [
        { name = "TABLE",              value = var.jobs_table_name },
        { name = "SITES_TABLE",        value = var.sites_table_name },
        { name = "BUCKET",             value = var.bucket_name },
        { name = "PINECONE_INDEX",     value = var.pinecone_index },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
      ]

      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = var.anthropic_secret_arn },
        { name = "GITHUB_TOKEN",      valueFrom = var.github_secret_arn },
        { name = "PINECONE_API_KEY",  valueFrom = var.pinecone_secret_arn },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "implementer"
        }
      }
    }
  ])
}
```

### `modules/ecs/outputs.tf`

```hcl
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.implementer.arn
}

output "security_group_id" {
  value = aws_security_group.fargate_tasks.id
}

output "container_name" {
  value = var.container_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.implementer.repository_url
}
```

---

## Observability Module Extension — `infra/modules/observability/`

Add to `modules/observability/variables.tf`:

```hcl
variable "ecs_log_group_name" {
  description = "CloudWatch log group name for ECS Fargate task logs"
}
```

Add to `modules/observability/main.tf`:

```hcl
resource "aws_cloudwatch_log_group" "ecs_tasks" {
  name              = var.ecs_log_group_name
  retention_in_days = 14
}
```

---

## Root File Extensions

### `infra/main.tf` — add ecs module

```hcl
module "ecs" {
  source = "./modules/ecs"

  iam_role_arn         = var.iam_role_arn
  ecr_repository_name  = "llms-txt-implementer"
  cluster_name         = "llms-txt-cluster"
  task_family          = "llms-txt-implementer"
  container_name       = "implementer"
  log_group_name       = "/ecs/llms-txt-implementer"
  aws_region           = var.aws_region

  bucket_name          = module.s3.bucket_name
  jobs_table_name      = module.dynamodb.jobs_table_name
  sites_table_name     = module.dynamodb.sites_table_name
  pinecone_index       = var.pinecone_index

  anthropic_secret_arn = var.anthropic_secret_arn
  github_secret_arn    = var.github_secret_arn
  pinecone_secret_arn  = var.pinecone_secret_arn
  vpc_id               = var.vpc_id
}
```

Also pass `ecs_log_group_name` when the observability module is wired in:

```hcl
module "observability" {
  source               = "./modules/observability"
  lambda_function_name = module.lambda.function_name
  api_gateway_id       = module.api_gateway.api_id
  ecs_log_group_name   = "/ecs/llms-txt-implementer"
}
```

### `infra/variables.tf` — add new variables

```hcl
variable "iam_role_arn" {
  description = "ARN of the existing IAM role used across all compute resources"
}

variable "github_secret_arn" {
  description = "Secrets Manager ARN for the GitHub personal access token"
  sensitive   = true
}

variable "vpc_id" {
  description = "VPC ID in which Fargate tasks run"
}

variable "subnet_ids" {
  description = "Comma-separated subnet IDs for Fargate task networking"
}
```

### `infra/outputs.tf` — add ecr output

```hcl
output "ecr_repository_url" {
  description = "Push Docker images here before running Fargate tasks"
  value       = module.ecs.ecr_repository_url
}
```

The Lambda handler also needs these env vars to dispatch tasks. Add them to the lambda module
call in `infra/main.tf`:

```hcl
module "lambda" {
  ...
  ecs_cluster          = module.ecs.cluster_name
  ecs_task_definition  = module.ecs.task_definition_arn
  ecs_container_name   = module.ecs.container_name
  ecs_security_group   = module.ecs.security_group_id
  ecs_subnet_ids       = var.subnet_ids
}
```

---

## Manual IAM Additions (Outside Terraform)

Add these two statements to the existing IAM role policy after `terraform apply`:

```json
{
  "Effect": "Allow",
  "Action": ["ecs:RunTask"],
  "Resource": "<task_definition_arn>"
},
{
  "Effect": "Allow",
  "Action": ["iam:PassRole"],
  "Resource": "<iam_role_arn>",
  "Condition": {
    "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" }
  }
}
```

Use `terraform output` to get the `task_definition_arn` after applying.

---

## Dockerfile Requirements

The implementer Docker image must include `git` and `gh` (GitHub CLI). Base your Dockerfile
on the existing Lambda image or a standard Python 3.11 image and add:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y git curl && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
      https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y gh && \
    rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app
RUN pip install -e .
```

Add a `Dockerfile.implementer` at the repo root. The build and push step is manual for now
(Phase 5 CI/CD concern):

```bash
docker build -f Dockerfile.implementer -t <ecr_repository_url>:latest .
docker push <ecr_repository_url>:latest
```

---

## Cost Estimate

### Infrastructure (monthly, low usage)

| Resource | Cost |
|---|---|
| ECR storage (1–2 GB image) | ~$0.15/month |
| ECS cluster | $0 (free) |
| CloudWatch Logs (task output) | ~$0.05/month |
| Security group | $0 |
| Fargate compute (10 runs × 45 min × 1 vCPU / 2 GB) | **~$0.38/month** |
| **Total infra** | **~$0.58/month** |

### Token costs (dominant factor)

Each implementation run makes many Claude API calls over 30–60 minutes.
With prompt caching (plan content is re-read each turn, so cache hit rate is high):

| Scenario | Tokens | Cost per run |
|---|---|---|
| Simple single-page UI | ~150K input / 50K output | ~$1.20 |
| Multi-component UI | ~400K input / 150K output | ~$3.00 |
| Complex multi-page UI | ~800K input / 300K output | ~$5.50 |

At 10 runs/month, expect **$12–$55/month in token costs** depending on UI complexity.
Infrastructure cost is negligible compared to tokens.

---

## Acceptance Criteria

- `terraform apply` creates ECR repo, ECS cluster, task definition, and security group without modifying S3 or DynamoDB
- Task definition references the existing IAM role — no new IAM resources created
- Secrets (Anthropic, GitHub, Pinecone) are injected via `secrets` (not `environment`) so they never appear in CloudWatch logs
- ECS log group exists in observability module with 14-day retention
- `ecr_repository_url` output is available after apply for the Docker push step
- Lambda module receives the ECS cluster name, task definition ARN, container name, security group ID, and subnet IDs as environment variables
- All resources in `us-east-1`
