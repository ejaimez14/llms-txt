# Component: ECS Fargate Infrastructure & Agent Migration (Plan 22)

## How to Use This Plan

You are doing two related things:

1. **Terraform infrastructure** — Add `infra/modules/ecs/` for the brand-new ECS resources and
   extend `infra/modules/observability/` with a CloudWatch log group.
2. **Agent migration** — Move crawler and UI planner to ECS Fargate for all models. The
   Fargate entry point routes internally: Claude uses the `claude-agent-sdk` for a multi-turn
   loop; OpenAI uses the agent factory. Report and compare stay as single Lambda calls — no
   iteration is needed there.

The IAM role already exists outside of Terraform — it is passed as a variable and reused for
both the ECS task execution role and the task role. No IAM resources are created here.

Dependencies:
- [17-terraform-hosting.md](17-terraform-hosting.md) — lambda and observability modules must exist first
- [21-ui-implementer-agent.md](21-ui-implementer-agent.md) — established the Fargate agent pattern

---

## Owner

Infra subagent (Terraform sections) + Backend subagent (agent migration sections)

## Output Files

```
infra/
  main.tf                    ← extend (add ecs module, update lambda env vars)
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
src/
  agents/
    crawler.py               ← rewrite (claude-agent-sdk path)
    ui_planner.py            ← rewrite (claude-agent-sdk path)
  services/
    fargate.py               ← extend (add trigger_crawler_task, trigger_ui_planner_task)
  tasks/
    crawler.py               ← new (Fargate entry point)
    ui_planner.py            ← new (Fargate entry point)
  handler.py                 ← extend (always dispatch Fargate for crawl and ui-plan)
tests/
  test_crawler.py            ← update
  test_ui_planner.py         ← update
```

---

## What Is Brand New vs. What Extends Existing

**New module — `infra/modules/ecs/`:**
- One ECR repository (all three Fargate agents share the same Docker image)
- One ECS cluster
- Three ECS task definitions: implementer, crawler, ui-planner
- Security group for Fargate tasks (outbound internet only)

**Extends existing — `infra/modules/observability/`:**
- CloudWatch log group for all ECS task stdout/stderr (shared)

**New code:**
- `src/tasks/crawler.py` and `src/tasks/ui_planner.py` — Fargate entry points
- Two new trigger functions in `src/services/fargate.py`

**Rewrites:**
- `src/agents/crawler.py` — always dispatches Fargate regardless of model; no in-Lambda execution
- `src/agents/ui_planner.py` — same pattern

**Manual IAM addition (outside Terraform):**
The existing IAM role needs these additional permissions for the Lambda function to dispatch
Fargate tasks. Add them to the role policy outside of Terraform:
- `ecs:RunTask` scoped to all three task definition ARNs
- `iam:PassRole` scoped to the same IAM role ARN (required by AWS when ECS assumes it)

---

## ECS Module — `infra/modules/ecs/`

### `modules/ecs/variables.tf`

```hcl
variable "iam_role_arn" {
  description = "ARN of the existing IAM role used for both task execution and task role"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository shared by all Fargate agents"
}

variable "cluster_name" {
  description = "Name of the ECS cluster"
}

variable "implementer_task_family" {
  description = "ECS task definition family name for the UI implementer"
}

variable "crawler_task_family" {
  description = "ECS task definition family name for the crawler agent"
}

variable "ui_planner_task_family" {
  description = "ECS task definition family name for the UI planner agent"
}

variable "task_cpu" {
  description = "vCPU units for Fargate tasks (1024 = 1 vCPU)"
  default     = 1024
}

variable "task_memory" {
  description = "Memory in MB for Fargate tasks"
  default     = 2048
}

variable "log_group_name" {
  description = "CloudWatch log group name for all Fargate task stdout/stderr"
}

variable "aws_region" {
  description = "AWS region for log configuration"
}

variable "bucket_name" {
  description = "S3 bucket name passed to containers as an environment variable"
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
  description = "Secrets Manager ARN for the GitHub token (implementer only)"
}

variable "pinecone_secret_arn" {
  description = "Secrets Manager ARN for the Pinecone API key"
}

variable "vpc_id" {
  description = "VPC ID for the Fargate task security group"
}
```

### `modules/ecs/main.tf`

All three task definitions use the same ECR image. Only the implementer mounts `GITHUB_TOKEN`.

```hcl
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
```

### `modules/ecs/outputs.tf`

```hcl
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "implementer_task_definition_arn" {
  value = aws_ecs_task_definition.implementer.arn
}

output "crawler_task_definition_arn" {
  value = aws_ecs_task_definition.crawler.arn
}

output "ui_planner_task_definition_arn" {
  value = aws_ecs_task_definition.ui_planner.arn
}

output "security_group_id" {
  value = aws_security_group.fargate_tasks.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.agents.repository_url
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

  iam_role_arn            = var.iam_role_arn
  ecr_repository_name     = "llms-txt-agents"
  cluster_name            = "llms-txt-cluster"
  implementer_task_family = "llms-txt-implementer"
  crawler_task_family     = "llms-txt-crawler"
  ui_planner_task_family  = "llms-txt-ui-planner"
  log_group_name          = "/ecs/llms-txt"
  aws_region              = var.aws_region

  bucket_name          = module.s3.bucket_name
  jobs_table_name      = module.dynamodb.jobs_table_name
  sites_table_name     = module.dynamodb.sites_table_name
  pinecone_index       = var.pinecone_index

  anthropic_secret_arn = var.anthropic_secret_arn
  github_secret_arn    = var.github_secret_arn
  pinecone_secret_arn  = var.pinecone_secret_arn
  vpc_id               = var.vpc_id
}

module "observability" {
  source               = "./modules/observability"
  lambda_function_name = module.lambda.function_name
  api_gateway_id       = module.api_gateway.api_id
  ecs_log_group_name   = "/ecs/llms-txt"
}
```

Pass all ECS env vars to the Lambda module so the handler can dispatch tasks:

```hcl
module "lambda" {
  ...
  ecs_cluster                    = module.ecs.cluster_name
  ecs_implementer_task_definition = module.ecs.implementer_task_definition_arn
  ecs_crawler_task_definition    = module.ecs.crawler_task_definition_arn
  ecs_ui_planner_task_definition = module.ecs.ui_planner_task_definition_arn
  ecs_security_group             = module.ecs.security_group_id
  ecs_subnet_ids                 = var.subnet_ids
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
  description = "Push agent Docker images here before running Fargate tasks"
  value       = module.ecs.ecr_repository_url
}
```

---

## Manual IAM Additions (Outside Terraform)

Add these statements to the existing IAM role policy after `terraform apply`. Use
`terraform output` to get the task definition ARNs:

```json
{
  "Effect": "Allow",
  "Action": ["ecs:RunTask"],
  "Resource": [
    "<implementer_task_definition_arn>",
    "<crawler_task_definition_arn>",
    "<ui_planner_task_definition_arn>"
  ]
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

---

## Dockerfile

All three Fargate agents share one Docker image. The implementer needs `git` and `gh`
(GitHub CLI) for branch creation and PR opening. Crawler and UI planner only need the
`claude-agent-sdk` and Python dependencies, but they use the same image for simplicity.

Add `Dockerfile.agent` at the repo root:

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

Build and push (manual for now — Phase 5 CI/CD concern):

```bash
docker build -f Dockerfile.agent -t <ecr_repository_url>:latest .
docker push <ecr_repository_url>:latest
```

---

## Crawler Fargate Task

### Design

The Fargate entry point routes on `model`. For Claude it runs the `claude-agent-sdk` loop:
Claude discovers pages from the root URL via `WebFetch`, iterates, then writes
`crawl-output.json` to the workspace. The entry point validates the JSON against `CrawlOutput`
and calls `JobHooks.on_complete`. For OpenAI it uses the existing agent factory
(`create_agent` / `run_agent`), which handles the hooks lifecycle internally.

Note: Anthropic's server-side `web_search_20250305` tool is not available through the SDK.
Claude discovers pages by fetching the root URL and following links from there — still a
quality improvement because Claude can iteratively decide which pages to fetch rather than
producing everything in one pass.

### `src/tasks/crawler.py`

```python
import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import CLAUDE_CRAWL_MODEL
from src.models import CrawlOutput
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger

logger = get_logger(__name__)

CRAWL_MAX_TURNS = 30
CRAWL_TIMEOUT_SECONDS = 1800
OUTPUT_FILE = "crawl-output.json"


def run_crawler_task(job_id: str, url: str, model: str) -> None:
    """Fargate entry point: routes to SDK loop (Claude) or agent factory (OpenAI)."""
    if model == "claude":
        _run_claude(job_id, url)
    else:
        _run_openai(job_id, url, model)


def _run_claude(job_id: str, url: str) -> None:
    """SDK-based crawl loop with manual hooks lifecycle."""
    hooks = JobHooks(job_id, "crawl", url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url))
    except Exception as exc:
        logger.error({"event": "crawler_task_failed", "error": str(exc)})
        hooks.on_error(exc)


def _run_openai(job_id: str, url: str, model: str) -> None:
    """Agent factory crawl — hooks lifecycle managed internally by run_agent."""
    agent = create_agent(
        model=model,
        agent_type="crawl",
        job_id=job_id,
        url=url,
        system_prompt=CRAWL_SYSTEM_PROMPT,
    )
    run_agent(agent, f"Crawl this website and produce an llms.txt file: {url}")


async def _run_sdk(hooks: JobHooks, url: str) -> None:
    """Runs the claude-agent-sdk loop, reads crawl-output.json, and completes the artifact."""
    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=CLAUDE_CRAWL_MODEL,
            permission_mode="bypassPermissions",
            allowed_tools=["WebFetch", "Write"],
            max_turns=CRAWL_MAX_TURNS,
        )
        await asyncio.wait_for(
            _exhaust(query(prompt=_build_prompt(url), options=options)),
            timeout=CRAWL_TIMEOUT_SECONDS,
        )
        output = CrawlOutput.model_validate_json(
            Path(workspace, OUTPUT_FILE).read_text()
        )
        hooks.on_complete(output.model_dump())


async def _exhaust(gen) -> None:
    async for message in gen:
        logger.info({"event": "crawler_message", "type": type(message).__name__})


def _build_prompt(url: str) -> str:
    """Combines system instructions with the file-writing requirement and target URL."""
    return (
        f"{CRAWL_SYSTEM_PROMPT}\n\n"
        f"After completing your analysis, write your output as a JSON object to "
        f"`{OUTPUT_FILE}` in the working directory. "
        f"The JSON must have exactly two fields: `llms_txt` (string) and `metadata` (object).\n\n"
        f"Crawl this website: {url}"
    )


if __name__ == "__main__":
    run_crawler_task(
        job_id=os.environ["CRAWLER_JOB_ID"],
        url=os.environ["CRAWLER_URL"],
        model=os.environ["CRAWLER_MODEL"],
    )
```

### `src/agents/crawler.py` — rewrite

The agent file becomes a thin dispatcher — always Fargate, regardless of model.

```python
from src.services.fargate import trigger_crawler_task


def run_crawler(job_id: str, url: str, model: str) -> None:
    """Dispatches the crawl job to Fargate for both Claude and OpenAI."""
    trigger_crawler_task(job_id, url, model)
```

---

## UI Planner Fargate Task

### Design

Identical pattern to the crawler. The entry point routes on `model`: Claude uses the SDK
and writes `ui-plan-output.json`; OpenAI uses the agent factory with its own hooks lifecycle.

### `src/tasks/ui_planner.py`

```python
import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import CLAUDE_UI_PLAN_MODEL
from src.models import UIPlanOutput
from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger

logger = get_logger(__name__)

UI_PLAN_MAX_TURNS = 20
UI_PLAN_TIMEOUT_SECONDS = 900
OUTPUT_FILE = "ui-plan-output.json"


def run_ui_planner_task(job_id: str, url: str, model: str) -> None:
    """Fargate entry point: routes to SDK loop (Claude) or agent factory (OpenAI)."""
    if model == "claude":
        _run_claude(job_id, url)
    else:
        _run_openai(job_id, url, model)


def _run_claude(job_id: str, url: str) -> None:
    """SDK-based UI planner loop with manual hooks lifecycle."""
    hooks = JobHooks(job_id, "ui-plan", url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url))
    except Exception as exc:
        logger.error({"event": "ui_planner_task_failed", "error": str(exc)})
        hooks.on_error(exc)


def _run_openai(job_id: str, url: str, model: str) -> None:
    """Agent factory UI plan — hooks lifecycle managed internally by run_agent."""
    agent = create_agent(
        model=model,
        agent_type="ui-plan",
        job_id=job_id,
        url=url,
        system_prompt=UI_PLAN_SYSTEM_PROMPT,
    )
    run_agent(agent, f"Analyze this website and produce a UI implementation plan: {url}")


async def _run_sdk(hooks: JobHooks, url: str) -> None:
    """Runs the claude-agent-sdk loop, reads ui-plan-output.json, and completes the artifact."""
    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=CLAUDE_UI_PLAN_MODEL,
            permission_mode="bypassPermissions",
            allowed_tools=["WebFetch", "Write"],
            max_turns=UI_PLAN_MAX_TURNS,
        )
        await asyncio.wait_for(
            _exhaust(query(prompt=_build_prompt(url), options=options)),
            timeout=UI_PLAN_TIMEOUT_SECONDS,
        )
        output = UIPlanOutput.model_validate_json(
            Path(workspace, OUTPUT_FILE).read_text()
        )
        hooks.on_complete(output.model_dump())


async def _exhaust(gen) -> None:
    async for message in gen:
        logger.info({"event": "ui_planner_message", "type": type(message).__name__})


def _build_prompt(url: str) -> str:
    """Combines system instructions with the file-writing requirement and target URL."""
    return (
        f"{UI_PLAN_SYSTEM_PROMPT}\n\n"
        f"After completing your analysis, write your output as a JSON object to "
        f"`{OUTPUT_FILE}` in the working directory. "
        f"The JSON must have exactly two fields: `plan_markdown` (string) and "
        f"`design_tokens` (object).\n\n"
        f"Analyze this website and produce a UI implementation plan: {url}"
    )


if __name__ == "__main__":
    run_ui_planner_task(
        job_id=os.environ["UI_PLANNER_JOB_ID"],
        url=os.environ["UI_PLANNER_URL"],
        model=os.environ["UI_PLANNER_MODEL"],
    )
```

### `src/agents/ui_planner.py` — rewrite

```python
from src.services.fargate import trigger_ui_planner_task


def run_ui_planner(job_id: str, url: str, model: str) -> None:
    """Dispatches the UI planning job to Fargate for both Claude and OpenAI."""
    trigger_ui_planner_task(job_id, url, model)
```

---

## Fargate Service Extension

Add to `src/services/fargate.py`:

```python
def trigger_crawler_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs run_crawler_task with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_CRAWLER_TASK_DEFINITION"],
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": os.environ["ECS_SUBNET_IDS"].split(","),
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [{
                    "name": "crawler",
                    "environment": [
                        {"name": "CRAWLER_JOB_ID", "value": job_id},
                        {"name": "CRAWLER_URL",    "value": url},
                        {"name": "CRAWLER_MODEL",  "value": model},
                    ],
                }]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_crawler_dispatch_failed", "error": str(exc)})
        raise


def trigger_ui_planner_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs run_ui_planner_task with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_UI_PLANNER_TASK_DEFINITION"],
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": os.environ["ECS_SUBNET_IDS"].split(","),
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [{
                    "name": "ui-planner",
                    "environment": [
                        {"name": "UI_PLANNER_JOB_ID", "value": job_id},
                        {"name": "UI_PLANNER_URL",    "value": url},
                        {"name": "UI_PLANNER_MODEL",  "value": model},
                    ],
                }]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_ui_planner_dispatch_failed", "error": str(exc)})
        raise
```

---

## Handler Amendment

The handler's crawl and ui-plan routes now always dispatch a Fargate task regardless of model.
`_run_in_thread` is no longer called for these agents — the entry point handles SDK selection.

```python
# src/handler.py — updated crawl route

@router.post("/crawl", status_code=202, summary="Crawl a website")
def crawl(req: CrawlRequest) -> dict:
    """Creates a crawl job and dispatches it to Fargate."""
    job_id = str(uuid.uuid4())
    create_job(job_id, req.url, req.model, JobType.CRAWL)
    trigger_crawler_task(job_id, req.url, req.model.value)
    return {"jobId": job_id, "status": "processing"}


# src/handler.py — updated ui-plan route (if it exists as a route)
# If ui-plan is currently triggered as part of the crawl job, adjust accordingly.
# The pattern is the same: always dispatch Fargate, pass the model string.
```

New imports needed in `handler.py`:

```python
from src.services.fargate import trigger_crawler_task, trigger_implementer_task, trigger_ui_planner_task
```

### Environment Variables

Add to `.env` for local testing. In Lambda, these come from the lambda module env config:

```
ECS_CLUSTER=llms-txt-cluster
ECS_IMPLEMENTER_TASK_DEFINITION=arn:aws:ecs:...
ECS_CRAWLER_TASK_DEFINITION=arn:aws:ecs:...
ECS_UI_PLANNER_TASK_DEFINITION=arn:aws:ecs:...
ECS_SUBNET_IDS=subnet-abc123,subnet-def456
```

Note: `ECS_TASK_DEFINITION` (used by the existing `trigger_implementer_task`) should be
renamed to `ECS_IMPLEMENTER_TASK_DEFINITION` for consistency. Update both `fargate.py` and
the lambda module wiring.

---

## Cost Estimate

### Infrastructure (monthly, low usage)

| Resource | Cost |
|---|---|
| ECR storage (1–2 GB shared image) | ~$0.15/month |
| ECS cluster | $0 (free) |
| CloudWatch Logs (all task output) | ~$0.10/month |
| Security group | $0 |
| Fargate compute — implementer (10 runs × 45 min × 1 vCPU / 2 GB) | ~$0.38/month |
| Fargate compute — crawler (50 runs × 10 min × 1 vCPU / 2 GB) | ~$0.22/month |
| Fargate compute — ui-planner (20 runs × 5 min × 1 vCPU / 2 GB) | ~$0.04/month |
| **Total infra** | **~$0.89/month** |

Token costs remain the dominant factor. Crawler and UI planner runs are shorter than the
implementer but still multi-turn. Expect $15–$65/month at moderate usage across all agents.

---

## Acceptance Criteria

**Terraform:**
- `terraform apply` creates ECR repo, ECS cluster, three task definitions, and security group without modifying S3 or DynamoDB
- All three task definitions reference the existing IAM role — no new IAM resources created
- `GITHUB_TOKEN` secret appears only in the implementer task definition
- Crawler and UI planner task definitions have only Anthropic and Pinecone secrets
- ECS log group exists in observability module with 14-day retention, shared by all three tasks
- `ecr_repository_url` output is available after apply for the Docker push step
- Lambda module receives the cluster name, all three task definition ARNs, security group ID, and subnet IDs as environment variables
- All resources in `us-east-1`

**Crawler Fargate task:**
- `run_crawler_task` calls `hooks.on_start()` before the SDK loop
- On agent success and valid JSON, `hooks.on_complete()` is called (which saves to S3, embeds, upserts Pinecone)
- On any failure (timeout, missing file, invalid JSON, SDK error), `hooks.on_error()` is called and the function does not re-raise
- Agent is capped at `max_turns=30` and a 30-minute `asyncio.wait_for` timeout
- The prompt appends the file-writing instruction after the system prompt — `CRAWL_SYSTEM_PROMPT` itself is unchanged

**UI Planner Fargate task:**
- Same lifecycle pattern as the crawler
- Agent is capped at `max_turns=20` and a 15-minute timeout

**Agent routing:**
- `run_crawler("job-1", url, "claude")` calls `trigger_crawler_task(job_id, url, "claude")`
- `run_crawler("job-1", url, "openai")` calls `trigger_crawler_task(job_id, url, "openai")`
- Both always dispatch Fargate — no in-Lambda fallback for crawl or ui-plan
- Same pattern for `run_ui_planner`
- Handler crawl route always calls `trigger_crawler_task` — no model branching in the handler

**Tests:**
- `test_run_crawler_dispatches_fargate_for_all_models` — `trigger_crawler_task` called with
  correct `model` arg for both "claude" and "openai"; `run_agent` is never called in the agent file
- Same test for `run_ui_planner`
- `test_run_crawler_task_claude_calls_hooks_on_success` — Claude path: `hooks.on_complete`
  called with validated CrawlOutput; no re-raise on success
- `test_run_crawler_task_claude_calls_hooks_on_error` — Claude path: `hooks.on_error` called
  on any exception (timeout, missing file, invalid JSON); function does not re-raise
- `test_run_crawler_task_openai_calls_agent_factory` — OpenAI path: `create_agent` and
  `run_agent` are called with `agent_type="crawl"` and the correct model
- Same three tests for `run_ui_planner_task`
