# Component: Terraform — Storage Modules (Phase 1)

## How to Use This Plan

You are implementing **Phase 1 Terraform** — the storage modules needed to run this project locally. Your job is to produce `infra/modules/s3/`, `infra/modules/dynamodb/`, and the root `infra/main.tf`, `variables.tf`, `outputs.tf` that wire them together.

A second agent will add the Lambda, API Gateway, and observability modules later (Phase 5). Write the root files so they can be extended — do not hardcode assumptions that these are the only modules.

Dependencies: **None** — implement and apply before Phase 4 local testing.

Related plans:
- [00-overview.md](00-overview.md) — full phased execution plan
- [17-terraform-hosting.md](17-terraform-hosting.md) — Phase 5 agent adds remaining modules to this same `infra/` root

---

## Owner

Infra subagent

## Output Files

```
infra/
  main.tf
  variables.tf
  outputs.tf
  terraform.tfvars.example
  modules/
    s3/
      main.tf
      variables.tf
      outputs.tf
    dynamodb/
      main.tf
      variables.tf
      outputs.tf
    secrets/
      main.tf
      variables.tf
      outputs.tf
```

---

## Resources to Create

### S3 Module (`modules/s3/`)

```hcl
resource "aws_s3_bucket" "results" {
  bucket = var.bucket_name
}

resource "random_id" "suffix" {
  byte_length = 4
}
```

- Bucket name: `crawler-output-${random_id.suffix.hex}` — random suffix for global uniqueness
- No public access — all access via presigned URLs or IAM credentials

### DynamoDB Module (`modules/dynamodb/`)

Two tables: `jobs` for run history (keyed by `jobId`) and `sites` for the canonical latest state per URL (keyed by `url`).

```hcl
# Jobs table — full run history, one record per crawl invocation
resource "aws_dynamodb_table" "jobs" {
  name         = var.jobs_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "jobId"

  attribute {
    name = "jobId"
    type = "S"
  }

  attribute {
    name = "url"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  # GSI for "give me all crawl runs for this URL, sorted by date"
  global_secondary_index {
    name            = "url-createdAt-index"
    hash_key        = "url"
    range_key       = "createdAt"
    projection_type = "ALL"
  }
}

# Sites table — one record per URL, always the latest successful crawl
resource "aws_dynamodb_table" "sites" {
  name         = var.sites_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"

  attribute {
    name = "url"
    type = "S"
  }
}
```

- `jobs` table name: `crawler-jobs`
- `sites` table name: `crawler-sites`
- Both use pay-per-request billing
- The `url-createdAt-index` GSI on `jobs` enables efficient per-URL history queries without a table scan

### Secrets Module (`modules/secrets/`)

Stores the Anthropic API key in AWS Secrets Manager. The application code always fetches it by name — no env var needed.

```hcl
resource "aws_secretsmanager_secret" "anthropic_key" {
  name = "llms-txt/anthropic-api-key"
}

resource "aws_secretsmanager_secret_version" "anthropic_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_key.id
  secret_string = jsonencode({ value = var.anthropic_api_key })
}

output "anthropic_secret_arn" {
  value = aws_secretsmanager_secret.anthropic_key.arn
}
```

The `anthropic_api_key` variable is sensitive — it comes from `terraform.tfvars` which is gitignored.

### Root `main.tf`

Wire in the three modules. Leave room for additional modules in Phase 5.

```hcl
provider "aws" {
  region = var.aws_region
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = "crawler-output"
}

module "dynamodb" {
  source           = "./modules/dynamodb"
  jobs_table_name  = "crawler-jobs"
  sites_table_name = "crawler-sites"
}

module "secrets" {
  source            = "./modules/secrets"
  anthropic_api_key = var.anthropic_api_key
}
```

---

## Variables (`infra/variables.tf`)

```hcl
variable "aws_region" {
  default = "us-east-1"
}

variable "anthropic_api_key" {
  sensitive   = true
  description = "Anthropic API key — written to Secrets Manager, never used directly by Lambda."
}
```

---

## Outputs (`infra/outputs.tf`)

```hcl
output "bucket_name" {
  value = module.s3.bucket_name
}

output "jobs_table_name" {
  value = module.dynamodb.jobs_table_name
}

output "sites_table_name" {
  value = module.dynamodb.sites_table_name
}

output "anthropic_secret_arn" {
  value = module.secrets.anthropic_secret_arn
}
```

Copy `bucket_name`, `jobs_table_name`, and `sites_table_name` into your local environment variables (`BUCKET`, `TABLE`, `SITES_TABLE`) before running the local dev server. The `anthropic_secret_arn` is referenced by the Lambda IAM policy in Phase 5.

---

## tfvars Files

`infra/terraform.tfvars.example` (committed — no real values):
```hcl
aws_region        = "us-east-1"
anthropic_api_key = ""
```

`infra/terraform.tfvars` (gitignored — fill in real values):
```hcl
aws_region        = "us-east-1"
anthropic_api_key = "sk-ant-..."
```

---

## How to Apply

```bash
cd infra
terraform init
terraform apply
# → outputs: bucket_name, table_name
```

---

## Acceptance Criteria

- `terraform apply` creates the S3 bucket, both DynamoDB tables, and Secrets Manager secret
- Outputs `bucket_name`, `jobs_table_name`, `sites_table_name`, and `anthropic_secret_arn`
- Secret value is stored under key `"value"` in the JSON secret string
- Root files are structured so Phase 5 can add more modules without conflicts
- No Lambda, no API Gateway, no IAM roles in this phase
