# Component: Observability + Logging

## How to Use This Plan

You are implementing **Component 16: Observability + Logging**. This has two parts:
- **Part A (Backend):** Produce `src/services/logger.py` — a structured logging utility used by SDK hooks
- **Part B (Infra):** Produce `infra/modules/observability/` — Terraform for CloudWatch logs and dashboard

Do not implement any agent logic. Agents don't call the logger directly — hooks do.

Dependencies: **None** — both parts are independently buildable.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — hooks import and use the logger
- [01-terraform-storage.md](01-terraform-storage.md) — wires in the observability module

---

## Owner

Infra subagent (Part B) + Backend subagent (Part A)

## Output Files

```
src/
  services/
    logger.py

infra/
  modules/
    observability/
      main.tf
      variables.tf
      outputs.tf
```

---

## Part A: Logging Utility (`src/services/logger.py`)

A thin wrapper around Python's standard `logging` module. Outputs structured JSON so CloudWatch logs are machine-searchable. Agents never import this directly — only hooks use it.

### Functions

```python
def get_logger(name: str):
    """
    Returns a configured Python logger with JSON formatting.
    Each log line is a single JSON object.
    """

def log_job_event(logger, event: str, job_id: str, **kwargs):
    """
    Logs a structured event with consistent fields.
    All extra kwargs are merged into the JSON output.
    """
```

### Output Format

Every log line must be a single JSON object:

```json
{
  "timestamp": "2026-06-04T10:00:00Z",
  "level": "INFO",
  "event": "crawl_started",
  "jobId": "abc123",
  "url": "https://example.com",
  "model": "claude"
}
```

### Events Logged by Hooks

| Hook event | Log event name | Extra fields |
|-----------|----------------|--------------|
| Agent starts | `{type}_started` | `url`, `model` |
| LLM call ends | `llm_call_completed` | `model`, `duration_ms`, `token_count` |
| S3 upload | `s3_upload` | `s3_key` |
| Agent completes | `{type}_completed` | `duration_ms`, `s3_key` |
| Agent errors | `{type}_failed` | `error` |

---

## Part B: Terraform Observability Module

### API Gateway Access Logs

Enable access logging on the API Gateway stage:

```hcl
resource "aws_apigatewayv2_stage" "default" {
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn
    format = jsonencode({
      requestId = "$context.requestId"
      ip        = "$context.identity.sourceIp"
      method    = "$context.httpMethod"
      path      = "$context.path"
      status    = "$context.status"
      latency   = "$context.responseLatency"
      time      = "$context.requestTime"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name              = "/aws/apigateway/crawler-api"
  retention_in_days = 14
}
```

### CloudWatch Dashboard

A single dashboard with four widgets using built-in Lambda and API Gateway metrics:

1. **Lambda Invocations** — count per time period
2. **Lambda Errors** — error count over time
3. **Lambda Duration** — average and p99 execution time
4. **API Gateway 4xx/5xx** — client and server error rates

```hcl
resource "aws_cloudwatch_dashboard" "crawler" {
  dashboard_name = "crawler-agent"
  dashboard_body = jsonencode({
    widgets = [
      # ... 4 metric widgets
    ]
  })
}
```

### Variables

No variables required — the module uses only the Lambda function name and API Gateway ID passed from the root.

---

## Acceptance Criteria

- API Gateway access logs are enabled and writing to CloudWatch
- CloudWatch dashboard exists with 4 widgets (invocations, errors, duration, 4xx/5xx)
- All Lambda log output (from hooks) is structured JSON
- Logger utility outputs one JSON object per line

---

## Tests (Part A only)

**File:** `tests/test_logger.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_log_output_is_valid_json` | happy | log line is parseable as JSON with `event`, `jobId`, and `timestamp` fields |
| `test_log_extra_kwargs_merged` | happy | additional kwargs passed to `log_job_event` appear in the JSON output |
