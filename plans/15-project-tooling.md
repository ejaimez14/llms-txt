# Component: Project Tooling

## How to Use This Plan

You are implementing **Component 15: Project Tooling**. This covers everything needed to work with the project locally and package it for deployment.

**Do Phase 1 (Setup) immediately — before writing any code.** You need `pyproject.toml` to install deps and the `Makefile` to run tests and the local server. Phase 5 (Build + Deploy) only runs after local testing passes.

Dependencies: **None** — implement before Phase 2.

Related plans:
- [01-terraform-storage.md](01-terraform-storage.md) — `make tf-apply` runs Terraform
- [02-lambda-handler.md](02-lambda-handler.md) — `make run` starts the local server
- [17-terraform-hosting.md](17-terraform-hosting.md) — `make build` packages the zip before Phase 5 apply

---

## Owner

DevOps subagent

## Output Files

```
pyproject.toml      ← Phase 1
Makefile            ← Phase 1
build.sh            ← Phase 5
README.md           ← Phase 5
```

---

## Phase 1 — Repo Setup

### `pyproject.toml`

```toml
[project]
name = "llms-txt-crawler"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic",           # direct Anthropic API; built-in web_search/web_fetch run server-side
    "boto3",               # S3, DynamoDB, Secrets Manager, Bedrock Titan embeddings
    "fastapi",
    "mangum",              # ASGI adapter — lets API Gateway invoke the FastAPI app as Lambda
    "uvicorn[standard]",   # local dev server
    "pinecone-client",
    # "openai",            # uncomment when Codex support is added
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-asyncio",
    "httpx",               # required by FastAPI TestClient
    "moto[s3,dynamodb]",   # AWS mocking for tests
    "pytest-mock",
    "ruff",
]
```

Install with:

```bash
uv venv
source .venv/bin/activate
uv sync
```

---

### `Makefile`

```makefile
.PHONY: format lint test run build tf-plan tf-apply

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check --fix src/ tests/

test:
	uv run pytest tests/ -v

run:
	uv run uvicorn src.handler:app --reload --port 8000

build:
	bash build.sh

tf-plan:
	cd infra && terraform plan

tf-apply:
	cd infra && terraform apply
```

| Target | When to use |
|--------|-------------|
| `make format` | Before committing — formats Python files in place |
| `make lint` | Before committing — auto-fixes safe issues, flags the rest |
| `make test` | Continuously during development |
| `make run` | Phase 4 — starts local server at `http://localhost:8000` with auto-reload |
| `make build` | Phase 5 — packages `lambda.zip` before deploying |
| `make tf-plan` | Preview infra changes (Phase 1 and Phase 5) |
| `make tf-apply` | Apply infra changes (Phase 1 and Phase 5) |

---

## Phase 5 — Build + Deploy

### `build.sh`

```bash
#!/bin/bash
set -e

# 1. Install production deps into ./package/
uv pip install --target ./package -r <(uv export --no-dev --format requirements-txt)

# 2. Copy src/ Python files into ./package/ — index.html is deployed to S3, not Lambda
cp -r src/*.py src/agents src/services ./package/

# 3. Zip ./package/ into lambda.zip
cd package && zip -r ../lambda.zip . && cd ..

echo "Build complete: lambda.zip"

# 4. Deploy frontend to S3 and invalidate CloudFront cache
FRONTEND_BUCKET=$(cd infra && terraform output -raw frontend_bucket_name)
DIST_ID=$(cd infra && terraform output -raw cloudfront_distribution_id)

aws s3 cp src/index.html s3://$FRONTEND_BUCKET/index.html
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"

echo "Frontend deployed and cache invalidated"
```

The Lambda zip path (`lambda.zip`) is passed to Terraform via the `lambda_zip_path` variable. The S3 upload requires `terraform apply` (from [20-cloudfront-auth.md](20-cloudfront-auth.md)) to have run first so the bucket and distribution exist.

---

### `README.md`

Include these sections:

#### Prerequisites
- AWS CLI configured (`s3:*`, `dynamodb:*`, `bedrock:InvokeModel` on Titan, `secretsmanager:GetSecretValue` on `llms-txt/anthropic-api-key`)
- Terraform >= 1.0
- Python 3.11
- [`uv`](https://docs.astral.sh/uv/) for package management
- Pinecone account (free tier) with an index created
- AWS account with Bedrock model access: `amazon.titan-embed-text-v1`

#### Setup

1. **Install dependencies**
   ```bash
   uv venv && source .venv/bin/activate && uv sync
   ```

2. **Apply Phase 1 infrastructure** (S3, DynamoDB, Secrets Manager)
   ```bash
   cp infra/terraform.tfvars.example infra/terraform.tfvars
   # Fill in anthropic_api_key, pinecone_api_key, and pinecone_index
   make tf-apply
   # → outputs: bucket_name, table_name
   ```

3. **Set local environment variables**
   ```bash
   export BUCKET="crawler-output-<suffix>"
   export TABLE="crawler-jobs"
   export PINECONE_API_KEY="..."
   export PINECONE_INDEX="..."
   # AWS_* creds already set — also used for Secrets Manager fetch
   ```

4. **Run locally**
   ```bash
   make run
   # → http://localhost:8000
   ```

#### Build and Deploy (Phase 5)

```bash
make build
make tf-apply
terraform -chdir=infra output api_url
terraform -chdir=infra output -raw api_key
```

#### API Usage

```bash
# Start a crawl
curl -X POST https://<api_url>/crawl \
  -H "x-api-key: <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "model": "claude"}'
# → {"jobId": "abc123", "status": "processing"}

# Poll for completion
curl "https://<api_url>/job?id=abc123" -H "x-api-key: <api_key>"

# Fetch artifact
curl "https://<api_url>/job/abc123/llms-txt" -H "x-api-key: <api_key>"

# Search
curl "https://<api_url>/search?q=pricing+pages" -H "x-api-key: <api_key>"
```

---

## Acceptance Criteria

- `uv sync` installs all deps from `pyproject.toml` with no errors
- `make format` rewrites Python files in place using ruff
- `make lint` exits non-zero on unfixable lint errors
- `make test` runs all tests under `tests/` with verbose output
- `make run` starts uvicorn at port 8000 with auto-reload
- `make build` produces `lambda.zip` at the project root
- `make tf-apply` runs `terraform apply` inside `infra/`
- `README.md` is sufficient to deploy from scratch with no prior context
