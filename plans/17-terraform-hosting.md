# Component: Terraform — Hosting Modules (Phase 5)

## How to Use This Plan

You are implementing **Phase 5 Terraform** — the modules needed to host this system on AWS. Your job is to add `infra/modules/lambda/`, `infra/modules/api_gateway/`, and `infra/modules/observability/`, and update the root `infra/main.tf`, `variables.tf`, and `outputs.tf` to wire them in.

The S3 and DynamoDB modules already exist from Phase 3. Do not modify them. Just add the new modules and extend the root files.

Dependencies: [01-terraform-storage.md](01-terraform-storage.md) must already be applied. Lambda zip must be built via [15-build-deploy-script.md](15-build-deploy-script.md).

Related plans:
- [00-overview.md](00-overview.md) — full phased execution plan
- [01-terraform-storage.md](01-terraform-storage.md) — storage modules already in place
- [16-observability-logging.md](16-observability-logging.md) — observability module spec
- [15-project-tooling.md](15-project-tooling.md) — produces the Lambda zip and deploys frontend to S3
- [19-scheduled-recrawl.md](19-scheduled-recrawl.md) — adds SQS queue, DLQ, EventBridge rule, and IAM additions to this module
- [20-cloudfront-auth.md](20-cloudfront-auth.md) — adds CloudFront distribution, S3 frontend bucket, and basic auth; apply after this module

---

## Owner

Infra subagent

## Output Files

```
infra/
  main.tf           ← extend (add lambda, api_gateway, observability modules)
  variables.tf      ← extend (add new variables)
  outputs.tf        ← extend (add api_url, api_key outputs)
  modules/
    lambda/
      main.tf
      variables.tf
      outputs.tf
    api_gateway/
      main.tf
      variables.tf
      outputs.tf
    observability/
      main.tf
      variables.tf
      outputs.tf
```

---

## Resources to Create

### Lambda Module (`modules/lambda/`)

- Function name: `crawler-agent`
- Runtime: Python 3.11
- Memory: 1024 MB
- Timeout: 120 seconds
- Reserved concurrent executions: 5 (cost safety)
- Source: `var.lambda_zip_path`
- Environment variables:
  - `BUCKET` — from `module.s3.bucket_name`
  - `TABLE` — from `module.dynamodb.jobs_table_name`
  - `SITES_TABLE` — from `module.dynamodb.sites_table_name`
  - `PINECONE_API_KEY` — from `var.pinecone_api_key`
  - `PINECONE_INDEX` — from `var.pinecone_index`
  - `RECRAWL_QUEUE_URL` — from `module.recrawl.queue_url` (added in Phase 5 with SQS)
  - _(No Anthropic API key env var — fetched from Secrets Manager by hardcoded name at cold start)_

**IAM execution role** (defined within the lambda module):
- S3: `PutObject`, `GetObject` scoped to the results bucket
- DynamoDB: `PutItem`, `GetItem`, `Query`, `UpdateItem`, `Scan` scoped to the jobs table
- Bedrock `InvokeModel` on:
  - `arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1` (embeddings only)
- Secrets Manager: `GetSecretValue` scoped to `var.anthropic_secret_arn` (output from Phase 1)
- CloudWatch Logs: standard Lambda logging policy

### API Gateway Module (`modules/api_gateway/`)

- HTTP API (not REST API)
- Routes (all prefixed `/api` — CloudFront routes `/api/*` here):
  - `POST /api/crawl`
  - `GET /api/job`
  - `GET /api/job/{id}/llms-txt`
  - `GET /api/job/{id}/plan`
  - `GET /api/jobs`
  - `GET /api/site`
  - `GET /api/search`
- API key authentication on **all** routes — CloudFront injects the key as a custom origin header so the browser never holds it. `GET /` is removed — frontend is served from S3 via CloudFront.
- Usage plan: 20 requests/day quota, 1 req/sec rate limit, burst 2
- Lambda permission for API Gateway invocation

### Observability Module (`modules/observability/`)

See [16-observability-logging.md](16-observability-logging.md) for full spec:
- CloudWatch log group for Lambda + API Gateway access logs
- CloudWatch dashboard: invocations, errors, duration, 4xx/5xx

---

## Root File Extensions

Add to `infra/main.tf`:
```hcl
module "lambda" {
  source                = "./modules/lambda"
  lambda_zip_path       = var.lambda_zip_path
  bucket_name           = module.s3.bucket_name
  table_name            = module.dynamodb.table_name
  pinecone_api_key      = var.pinecone_api_key
  pinecone_index        = var.pinecone_index
  anthropic_secret_arn  = module.secrets.anthropic_secret_arn
}

module "api_gateway" {
  source             = "./modules/api_gateway"
  lambda_invoke_arn  = module.lambda.invoke_arn
  lambda_function_name = module.lambda.function_name
}

module "observability" {
  source               = "./modules/observability"
  lambda_function_name = module.lambda.function_name
  api_gateway_id       = module.api_gateway.api_id
}
```

Add to `infra/variables.tf`:
```hcl
variable "lambda_zip_path" {}

variable "pinecone_api_key" {
  sensitive = true
}

variable "pinecone_index" {}

```

Add to `infra/outputs.tf`:
```hcl
output "api_url" {
  value = module.api_gateway.api_url
}

output "api_key" {
  value     = module.api_gateway.api_key
  sensitive = true
}
```

Update `infra/terraform.tfvars.example` to include the new variables:
```hcl
aws_region       = "us-east-1"
lambda_zip_path  = "../lambda.zip"
pinecone_api_key = ""
pinecone_index   = ""
```

---

## How to Apply

```bash
# Build the Lambda zip first
./build.sh

# Fill in new variables in infra/terraform.tfvars, then apply
cd infra
terraform apply
# S3 and DynamoDB are unchanged; Lambda + API GW + observability are added
```

---

## Acceptance Criteria

- `terraform apply` adds Lambda, API Gateway, and observability without modifying S3 or DynamoDB
- Lambda can reach the existing S3 bucket and both DynamoDB tables
- API key auth enforced on all routes — no public routes
- Outputs `api_url` and `api_key` (consumed by `module.cloudfront` in [20-cloudfront-auth.md](20-cloudfront-auth.md))
- All resources in `us-east-1`
