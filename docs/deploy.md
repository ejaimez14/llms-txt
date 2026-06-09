# Deployment

## Prerequisites

- AWS account with an existing IAM role that has permissions for Lambda, ECS, S3, DynamoDB, SQS, CloudFront, and API Gateway
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- [uv](https://docs.astral.sh/uv/)
- A [Pinecone](https://pinecone.io) index (dimension: 1536, metric: cosine)
- API keys stored in AWS Secrets Manager:
  - `secrets/anthropic-api-key` → `{ "value": "<key>" }`
  - `secrets/pinecone-api-key` → `{ "value": "<key>" }`
  - `secrets/openai-api-key` → `{ "value": "<key>" }` (optional)

---

## 1. Build the Lambda zip

```bash
make build
# produces lambda.zip at the repo root
```

---

## 2. Create terraform.tfvars

```hcl
iam_role_arn        = "arn:aws:iam::ACCOUNT_ID:role/your-role"
pinecone_index      = "your-index-name"
vpc_id              = "vpc-xxx"
subnet_ids          = "subnet-xxx,subnet-yyy"
basic_auth_password = "a-strong-password"
```

`terraform.tfvars` is gitignored — never commit it.

---

## 3. Apply

```bash
make tf-plan    # review what will be created
make tf-apply   # deploy
```

---

## 4. Upload the frontend

```bash
terraform -chdir=infra output frontend_bucket_name
# → llms-txt-frontend-xxx

aws s3 cp src/index.html s3://<frontend_bucket_name>/index.html

terraform -chdir=infra output cloudfront_distribution_id
# invalidate cache so CloudFront serves the new file
aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
```

---

## 5. Build and push the agent image

```bash
terraform -chdir=infra output ecr_repository_url
# → ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/llms-txt-agents

aws ecr get-login-password | docker login --username AWS --password-stdin <ecr_url>
docker build -f Dockerfile.agent -t <ecr_url>:latest .
docker push <ecr_url>:latest
```

---

## 6. Set up local .env

Copy the Terraform outputs into `.env` for local development:

```bash
BUCKET=llms-txt-crawler-output
TABLE=llms-txt-jobs
SITES_TABLE=llms-txt-sites
PINECONE_INDEX=your-index-name
ECS_CLUSTER=llms-txt-cluster
ECS_TASK_DEFINITION=arn:aws:ecs:us-east-1:ACCOUNT_ID:task-definition/llms-txt-agent:1
ECS_SUBNET_IDS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUP=sg-xxx
RECRAWL_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/llms-txt-recrawl
```

Then run `make run` to start the API locally on port 8000.
