# Execution Overview

This document defines the build order. The goal is to stand up real AWS storage first, then build and test code locally against it, and only deploy to Lambda once everything works.

---

## Phased Execution Plan

### Phase 1 — Local Infrastructure (storage only)

Stand up S3 and DynamoDB before writing any code. The storage services and agents use these directly during local testing.

| File | What it produces |
|------|-----------------|
| [01-terraform-storage.md](01-terraform-storage.md) | `infra/modules/s3/`, `infra/modules/dynamodb/`, `infra/modules/secrets/`, root `main.tf` wiring |
| [15-project-tooling.md](15-project-tooling.md) *(Phase 1 section)* | `pyproject.toml`, `Makefile` — install deps and run dev commands from day one |

**AWS credentials required:**
```bash
export AWS_ACCESS_KEY_ID="AKIAxxxxxxxxxx"
export AWS_SECRET_ACCESS_KEY="xxxxxxxxxxxxxxxx"
export AWS_DEFAULT_REGION="us-east-1"
```

Your IAM user needs: `s3:*`, `dynamodb:*`, `bedrock:InvokeModel` on Titan Embeddings, and `secretsmanager:GetSecretValue` on `llms-txt/anthropic-api-key`.
Claude is accessed via the direct Anthropic API — the key is fetched from Secrets Manager, created in this phase.

```bash
cd infra
terraform init
terraform apply
# → outputs: bucket_name, table_name
```

---

### Phase 2 — Services (all parallel, no dependencies)

Build these simultaneously once Phase 1 infrastructure is up. Start with `04` first — all other services import from it.

| File | What it produces |
|------|-----------------|
| [04-models-constants-prompts.md](04-models-constants-prompts.md) | `src/constants.py`, `src/models.py`, `src/prompts.py` — enums, Pydantic models, agent system prompts |
| [03-storage-service.md](03-storage-service.md) | `src/services/storage.py` — S3 + DynamoDB operations |
| [05-embeddings-service.md](05-embeddings-service.md) | `src/services/embeddings.py` — Bedrock Titan wrapper |
| [06-pinecone-service.md](06-pinecone-service.md) | `src/services/pinecone_client.py` — vector upsert + query |
| [07-agent-factory-hooks.md](07-agent-factory-hooks.md) | `src/services/llm.py` + `src/services/hooks.py` — agent factory + lifecycle hooks |
| [16-observability-logging.md](16-observability-logging.md) *(Part A only)* | `src/services/logger.py` — structured JSON logger |

---

### Phase 3 — Agents + Handler (depends on Phase 2)

Build these once the services and factory exist. All can be built in parallel once Phase 2 is done.

A single `POST /crawl` request starts both agents in parallel under the same `job_id`. Each has its own system prompt and produces one artifact.

| File | What it produces | Artifact |
|------|-----------------|----------|
| [08-crawl-agent.md](08-crawl-agent.md) | `src/agents/crawler.py` | `llmsTxt` — llms.txt format |
| [10-ui-planner-agent.md](10-ui-planner-agent.md) | `src/agents/ui_planner.py` | `plan` — UI implementation plan markdown |
| [13-search-endpoint.md](13-search-endpoint.md) | `src/agents/search.py` | (synchronous GET, no artifact) |
| [02-lambda-handler.md](02-lambda-handler.md) | `src/handler.py` — FastAPI app + Mangum Lambda adapter |
| [14-frontend-ui.md](14-frontend-ui.md) | `src/index.html` |

---

### Phase 4 — Local Testing

Set environment variables and run the local dev server. Verify every endpoint works end-to-end before touching hosting infra.

**Environment variables:**
```bash
# From Phase 1 terraform outputs:
export BUCKET="crawler-output-<suffix>"
export TABLE="crawler-jobs"
export SITES_TABLE="crawler-sites"

# Pinecone:
export PINECONE_API_KEY="your-pinecone-key"
export PINECONE_INDEX="your-index-name"

# AWS creds already set above — used for S3, DynamoDB, Bedrock Titan embeddings,
# and Secrets Manager (Anthropic key is fetched from Secrets Manager automatically)
```

**Run the local server:**
```bash
make run
# → serving at http://localhost:8000
```

Open `http://localhost:8000` to test the UI, or use curl for individual endpoints.

---

### Phase 5 — AWS Deployment

Only once local testing passes. Run a plain `terraform apply` on the same `infra/` root — it adds Lambda, API Gateway, IAM, and observability on top of the already-existing storage resources.

| File | What it produces/provisions |
|------|-----------------------------|
| [15-project-tooling.md](15-project-tooling.md) *(Phase 5 section)* | `build.sh`, `README.md` — packages Lambda zip |
| [17-terraform-hosting.md](17-terraform-hosting.md) | `infra/modules/lambda/`, `api_gateway/` — adds hosting modules, extends root files |
| [16-observability-logging.md](16-observability-logging.md) *(Part B)* | `infra/modules/observability/` — CloudWatch dashboard and metrics |
| [19-scheduled-recrawl.md](19-scheduled-recrawl.md) | EventBridge cron + SQS queue + DLQ — daily re-crawl of all indexed URLs |
| [20-cloudfront-auth.md](20-cloudfront-auth.md) | CloudFront distribution + S3 frontend bucket + CloudFront Function basic auth — apply after `17` |

```bash
# Build the Lambda zip
make build

# Apply remaining infrastructure (storage resources are unchanged)
cd infra
terraform apply
```

---

## Infrastructure Layout

```
infra/
  main.tf
  variables.tf
  outputs.tf
  terraform.tfvars.example   ← committed, no real values
  terraform.tfvars            ← gitignored, your real values
  modules/
    s3/
    dynamodb/
    lambda/
    api_gateway/
    observability/
```

One directory, one state file. Phase 1 agent writes the storage modules. Phase 5 agent adds the hosting modules.

---

## What Needs AWS Credentials Locally

| Service | Used in | Auth method |
|---------|---------|-------------|
| Claude (LLM) | Agent factory | Secrets Manager — `llms-txt/anthropic-api-key` (fetched via IAM) |
| Bedrock (Titan Embeddings) | Embeddings service | IAM credentials (`AWS_*` env vars) |
| S3 | Storage service | IAM credentials |
| DynamoDB | Storage service | IAM credentials |
| Pinecone | Pinecone service | `PINECONE_API_KEY` env var |
