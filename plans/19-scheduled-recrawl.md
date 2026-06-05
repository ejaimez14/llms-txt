# Component: Scheduled Re-Crawl (EventBridge + SQS)

## How to Use This Plan

You are implementing **Component 19: Scheduled Re-Crawl**. Your job is to add a daily scheduled re-crawl pipeline that refreshes the llms.txt file and UI plan for every previously crawled URL. This is a **Phase 5 addition** — implement it after the core HTTP API is working.

No new Lambda function is needed. The existing Lambda gets two new handler paths (scheduler + worker) alongside the existing HTTP path. The dispatch happens at the top of the Lambda entrypoint before Mangum.

Dependencies:
- [02-lambda-handler.md](02-lambda-handler.md) — existing handler; you will modify the entrypoint and add two new handler paths
- [03-storage-service.md](03-storage-service.md) — add `list_all_crawled_urls()` here
- [17-terraform-hosting.md](17-terraform-hosting.md) — add all new AWS resources here

Related plans:
- [08-crawl-agent.md](08-crawl-agent.md) — re-crawl runs the same `run_crawler` function
- [10-ui-planner-agent.md](10-ui-planner-agent.md) — re-crawl also re-runs `run_ui_planner`
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — hooks fire exactly as in a normal crawl

---

## Owner

Backend + DevOps subagent

## Output Files

Modifications only — no new files:

```
src/
  handler.py            ← new entrypoint dispatch + two new handler paths
  services/
    storage.py          ← new list_all_crawled_urls() function
infra/
  main.tf               ← new SQS, DLQ, EventBridge resources
  (Lambda IAM additions)
```

---

## Architecture

```
EventBridge (cron: rate(1 day))
    │
    ▼ invokes
Lambda (scheduler path)
    │  scans DynamoDB for all completed crawl URLs
    │  writes one SQS message per URL
    ▼
SQS Queue
    │  event source mapping — one Lambda invocation per message
    ▼
Lambda (worker path)
    │  run_crawler + run_ui_planner in parallel (ThreadPoolExecutor)
    │  hooks fire exactly as in a normal POST /crawl
    ▼
S3 + DynamoDB + Pinecone  (same persistence layer as normal crawls)
```

Failed messages are retried up to `maxReceiveCount` times, then routed to the DLQ where they are visible in CloudWatch for inspection and manual replay.

---

## Part A: Lambda Entrypoint Dispatch (`src/handler.py`)

The existing `handler = Mangum(app)` line must be replaced so EventBridge and SQS events are caught before Mangum sees them.

```python
# Before (current):
handler = Mangum(app)

# After:
_mangum_handler = Mangum(app)

def handler(event, context):
    """Lambda entrypoint — dispatches to the correct handler path by event shape."""
    records = event.get("Records", [])
    if records and records[0].get("eventSource") == "aws:sqs":
        return handle_sqs(event, context)
    if event.get("source") == "aws.events":
        return handle_schedule(event, context)
    return _mangum_handler(event, context)
```

The Terraform `handler` variable stays `"handler.handler"` — no change needed there.

---

## Part B: Scheduler Path (`handle_schedule`)

Triggered once per day by EventBridge. Scans DynamoDB for all previously crawled URLs and enqueues one SQS message per URL.

```python
import json
import os
import boto3

def handle_schedule(event, context):
    """
    EventBridge cron handler. Scans DynamoDB for all completed crawl URLs
    and writes one SQS message per URL to trigger a re-crawl.
    """
    sqs = boto3.client("sqs")
    queue_url = os.environ["RECRAWL_QUEUE_URL"]

    urls = list_all_crawled_urls()  # new storage function — see Part D

    for item in urls:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"url": item["url"], "model": item["model"]}),
        )

    return {"scheduled": len(urls)}
```

`RECRAWL_QUEUE_URL` is injected as a Lambda environment variable from the Terraform `aws_sqs_queue` resource URL output.

---

## Part C: Worker Path (`handle_sqs`)

Triggered by SQS — one invocation per message (batch size 1). Creates a new job and runs both agents in parallel, identical to a normal `POST /crawl`.

```python
from concurrent.futures import ThreadPoolExecutor
import uuid

def handle_sqs(event, context):
    """
    SQS worker handler. Each record is one URL to re-crawl.
    Creates a new job_id per record so history is preserved — old crawl records are not overwritten.
    Both agents run in parallel via ThreadPoolExecutor, same as POST /crawl.
    Raising an exception causes SQS to retry the message (up to maxReceiveCount).
    """
    for record in event["Records"]:
        body = json.loads(record["body"])
        url = body["url"]
        model = body["model"]

        job_id = str(uuid.uuid4())
        create_job(job_id, url, model)
        _run_crawl_agents(job_id, url, model)  # existing helper from POST /crawl path

    return {"processed": len(event["Records"])}
```

**History preserved:** each re-crawl creates a new `job_id`. Old records remain in DynamoDB so you can compare crawl results over time. The History tab in the UI will show multiple entries per URL.

---

## Part D: Storage Function

No new function needed. The scheduler calls `list_sites()` from `src/services/storage.py` (added as part of the two-table design in [03-storage-service.md](03-storage-service.md)).

`list_sites()` scans the `crawler-sites` table — one record per URL, always the latest model. This replaces the previous approach of scanning the `jobs` table and deduplicating manually. The sites table already does that deduplication at write time via `upsert_site()`.

```python
def handle_schedule(event, context):
    sqs = boto3.client("sqs")
    queue_url = os.environ["RECRAWL_QUEUE_URL"]

    sites = list_sites()  # one record per unique URL, no deduplication needed

    for site in sites:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"url": site["url"], "model": site["model"]}),
        )

    return {"scheduled": len(sites)}
```

---

## Part E: Terraform (`infra/main.tf` additions)

Add inside the Phase 5 Terraform alongside the Lambda and API Gateway resources.

### SQS Queues

```hcl
resource "aws_sqs_queue" "recrawl_dlq" {
  name                      = "llms-txt-recrawl-dlq"
  message_retention_seconds = 1209600  # 14 days — enough time to inspect and replay
}

resource "aws_sqs_queue" "recrawl" {
  name                       = "llms-txt-recrawl"
  visibility_timeout_seconds = 900  # must be >= Lambda timeout to prevent double-processing
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.recrawl_dlq.arn
    maxReceiveCount     = 3  # retry 3× before routing to DLQ
  })
}
```

`visibility_timeout_seconds` must match the Lambda `timeout` setting in the existing Lambda resource. If a crawl takes longer than this, SQS will re-enqueue the message before Lambda finishes — causing duplicate runs.

### SQS → Lambda Event Source Mapping

```hcl
resource "aws_lambda_event_source_mapping" "recrawl_sqs" {
  event_source_arn = aws_sqs_queue.recrawl.arn
  function_name    = aws_lambda_function.api.arn
  batch_size       = 1  # one URL per invocation — simpler error handling, no partial batch failures
  enabled          = true
}
```

`batch_size = 1` means a single failed crawl doesn't block other URLs in the same batch.

### EventBridge Scheduled Rule

```hcl
resource "aws_cloudwatch_event_rule" "daily_recrawl" {
  name                = "llms-txt-daily-recrawl"
  schedule_expression = "rate(1 day)"
  description         = "Triggers daily re-crawl of all indexed URLs"
}

resource "aws_cloudwatch_event_target" "daily_recrawl" {
  rule      = aws_cloudwatch_event_rule.daily_recrawl.name
  target_id = "LambdaRecrawlScheduler"
  arn       = aws_lambda_function.api.arn
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_recrawl.arn
}
```

### Lambda Environment Variable Addition

Add to the existing Lambda `environment` block:

```hcl
RECRAWL_QUEUE_URL = aws_sqs_queue.recrawl.url
```

### IAM Additions

Add to the existing Lambda IAM role policy:

```hcl
# SQS — scheduler path sends messages; worker path consumes them
{
  Effect   = "Allow"
  Action   = ["sqs:SendMessage"]
  Resource = [aws_sqs_queue.recrawl.arn]
},
{
  Effect   = "Allow"
  Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
  Resource = [aws_sqs_queue.recrawl.arn, aws_sqs_queue.recrawl_dlq.arn]
}
```

---

## Acceptance Criteria

- EventBridge fires `handle_schedule` — confirmed by CloudWatch log entry `"scheduled": N`
- `handle_schedule` writes exactly one SQS message per unique crawled URL, no duplicates
- `handle_sqs` creates a new `job_id` per record — old job records are preserved
- Both agents (crawl + ui-plan) run in parallel for each re-crawled URL, identical to `POST /crawl`
- If `run_crawler` or `run_ui_planner` raises, the Lambda invocation fails → SQS retries the message
- After `maxReceiveCount` failures, the message lands in the DLQ (verifiable in AWS Console)
- `visibility_timeout_seconds` on the queue equals the Lambda timeout — no double-processing
- `RECRAWL_QUEUE_URL` env var injected from Terraform — no hardcoded queue URLs
- Normal HTTP traffic via API Gateway is completely unaffected

---

## Tests

**File:** `tests/test_scheduled_recrawl.py`
Use `pytest`. Mock AWS with `moto[sqs,dynamodb,s3]`. Mock agents with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_handle_schedule_enqueues_one_message_per_url` | happy | N sites in `crawler-sites` → N SQS messages enqueued |
| `test_handle_sqs_creates_new_job_id` | happy | each SQS record produces a new `job_id` — old records preserved |
| `test_handle_sqs_runs_both_agents` | happy | both `run_crawler` and `run_ui_planner` called per record |
| `test_handle_sqs_raises_on_agent_failure` | unhappy | exception from agent propagates so SQS retries the message |
