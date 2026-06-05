# Component: CloudFront Distribution + Basic Auth

## How to Use This Plan

You are implementing **Component 20: CloudFront Distribution + Basic Auth**. This is a **Phase 5 addition** implemented alongside [17-terraform-hosting.md](17-terraform-hosting.md).

Two responsibilities in one component:
1. **CloudFront distribution** — serves the frontend from S3 and routes `/api/*` to API Gateway. Lambda stops serving the UI entirely.
2. **Basic auth** — a CloudFront Function that gates the entire site (both the UI and the API) behind a username/password. Credentials are Terraform variables — never in source code.

**Upgrade path:** basic auth is intentionally simple. When you want real user management, replace the CloudFront Function with a Cognito User Pool + Lambda@Edge JWT validator. The CloudFront distribution structure stays identical — only the auth mechanism changes.

Dependencies: [17-terraform-hosting.md](17-terraform-hosting.md) must be applied first (API Gateway URL needed as CloudFront origin). [15-project-tooling.md](15-project-tooling.md) — `build.sh` uploads `index.html` to S3 as part of deploy.

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — `GET /` removed; all routes prefixed `/api`
- [14-frontend-ui.md](14-frontend-ui.md) — API calls use `/api/*`; no API key in JS
- [15-project-tooling.md](15-project-tooling.md) — `build.sh` adds S3 upload step

---

## Owner

Infra subagent

## Output Files

```
infra/
  modules/
    cloudfront/
      main.tf
      variables.tf
      outputs.tf
      functions/
        basic_auth.js.tpl   ← templatefile — credentials injected at plan time
```

---

## Architecture

```
Browser
  └─► CloudFront (basic auth on every request)
        ├─► /* → S3 bucket (index.html)
        └─► /api/* → API Gateway → Lambda
                          ↑
                   x-api-key injected as
                   custom origin header
                   (never visible to browser)
```

The API key never appears in the frontend JS. CloudFront holds it as a custom origin header and injects it on every `/api/*` request forwarded to API Gateway. The browser only ever talks to CloudFront.

---

## Part A: S3 Frontend Bucket

A dedicated bucket for the static frontend — separate from the results bucket so lifecycle policies and access controls don't collide.

```hcl
resource "aws_s3_bucket" "frontend" {
  bucket = "llms-txt-frontend-${random_id.suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "llms-txt-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.app.arn
        }
      }
    }]
  })
}
```

S3 is fully private — only CloudFront (via OAC) can read from it.

---

## Part B: CloudFront Function — Basic Auth

A viewer-request function that checks for a valid `Authorization: Basic` header on every request. Applied to both behaviors so the entire site (frontend + API) is gated.

**`infra/modules/cloudfront/functions/basic_auth.js.tpl`:**

```javascript
function handler(event) {
    var request = event.request;
    var authHeader = request.headers['authorization'];

    if (!authHeader || authHeader.value !== 'Basic ${base64_credentials}') {
        return {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {
                'www-authenticate': { value: 'Basic realm="llms-txt"' }
            }
        };
    }

    return request;
}
```

`${base64_credentials}` is filled in by Terraform's `templatefile()` at plan time — the plaintext credentials never appear in the deployed function code.

```hcl
resource "aws_cloudfront_function" "basic_auth" {
  name    = "llms-txt-basic-auth"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = templatefile("${path.module}/functions/basic_auth.js.tpl", {
    base64_credentials = base64encode(
      "${var.basic_auth_user}:${var.basic_auth_password}"
    )
  })
}
```

---

## Part C: CloudFront Distribution

Two origins, two behaviors, one function protecting both.

```hcl
resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US + Europe only — cheapest

  # Origin 1: S3 for frontend static files
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3Frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Origin 2: API Gateway — x-api-key injected here, never in browser JS
  origin {
    domain_name = replace(var.api_gateway_endpoint, "https://", "")
    origin_id   = "APIGateway"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "x-api-key"
      value = var.api_gateway_key
    }
  }

  # Default behavior: serve frontend from S3
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3Frontend"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  # /api/* behavior: forward to API Gateway, no caching
  ordered_cache_behavior {
    path_pattern    = "/api/*"
    allowed_methods = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods  = ["GET", "HEAD"]
    target_origin_id       = "APIGateway"
    viewer_protocol_policy = "https-only"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.basic_auth.arn
    }

    forwarded_values {
      query_string = true
      headers      = ["Content-Type"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
```

`PriceClass_100` restricts edge locations to US and Europe — keeps costs minimal and is fine for a demo.

---

## Part D: Variables and Outputs

**`variables.tf` additions:**

```hcl
variable "api_gateway_endpoint" {
  description = "API Gateway invoke URL (from module.api_gateway output)"
}

variable "api_gateway_key" {
  sensitive   = true
  description = "API Gateway key — injected as CloudFront custom origin header"
}

variable "basic_auth_user" {
  description = "Username for CloudFront basic auth"
  default     = "demo"
}

variable "basic_auth_password" {
  sensitive   = true
  description = "Password for CloudFront basic auth — share with interviewers"
}
```

**`outputs.tf` additions:**

```hcl
output "cloudfront_url" {
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
  description = "Public URL — share this with interviewers"
}

output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.id
}
```

**`terraform.tfvars.example` additions:**

```hcl
basic_auth_user     = "demo"
basic_auth_password = ""        # set before applying
```

---

## Part E: Wiring into Root `main.tf`

```hcl
module "cloudfront" {
  source               = "./modules/cloudfront"
  api_gateway_endpoint = module.api_gateway.api_url
  api_gateway_key      = module.api_gateway.api_key
  basic_auth_user      = var.basic_auth_user
  basic_auth_password  = var.basic_auth_password
}
```

---

## Deploying the Frontend

After `terraform apply`, upload `index.html` to S3 (handled by `build.sh` — see [15-project-tooling.md](15-project-tooling.md)):

```bash
FRONTEND_BUCKET=$(cd infra && terraform output -raw frontend_bucket_name)
aws s3 cp src/index.html s3://$FRONTEND_BUCKET/index.html
```

CloudFront caches aggressively. After updating `index.html`, invalidate:

```bash
DIST_ID=$(cd infra && terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

Add `cloudfront_distribution_id` as an output in Terraform for this.

---

## Upgrading to Cognito (when ready)

Replace `aws_cloudfront_function.basic_auth` with a Lambda@Edge function that:
1. Redirects unauthenticated users to Cognito hosted UI
2. Validates the JWT in the `Cookie` header on return
3. Allows the request through if the token is valid and not expired

The CloudFront distribution, S3 bucket, and API Gateway origin config stay identical. Only the `function_association` blocks change — swap the CloudFront Function ARN for the Lambda@Edge ARN.

---

## Acceptance Criteria

- `GET https://<cloudfront_url>/` without auth returns 401 and `www-authenticate` header
- Browser prompts for username/password — correct credentials load the frontend
- `GET https://<cloudfront_url>/api/job?id=...` routes to Lambda with `x-api-key` injected
- API Gateway URL is not referenced anywhere in `index.html`
- S3 bucket has no public access — direct S3 URL returns 403
- CloudFront serves `index.html` as the default root object
- `make deploy-frontend` (or equivalent) uploads and invalidates in one step

---

## Tests

No unit tests — this is pure infrastructure. Verify manually after `terraform apply`:

| Check | How |
|---|---|
| Auth gate works | `curl https://<cf_url>/` returns 401 |
| Correct credentials pass | `curl -u demo:<password> https://<cf_url>/` returns HTML |
| API routes correctly | `curl -u demo:<password> https://<cf_url>/api/job?id=x` returns 404 from Lambda (not CloudFront) |
| API key not in HTML | `curl -u demo:<password> https://<cf_url>/` — inspect response, no API key string present |
| S3 not public | Direct S3 URL returns 403 |
