# Component: Storage Service

## How to Use This Plan

You are implementing **Component 3: Storage Service**. Your job is to produce `src/services/storage.py`. This module is a shared dependency used by the agent hooks and the Lambda handler — keep it stateless and side-effect-free (pure I/O, no business logic).

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `JobStatus`, `ArtifactType`, `ArtifactStatus`, `JobRecord`, `JobSummary` from there. No AWS environment required beyond that.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — hooks call `complete_artifact` and `fail_artifact`
- [02-lambda-handler.md](02-lambda-handler.md) — handler calls `create_job`, `get_job`, `get_artifact_content`, `list_jobs`
- [19-scheduled-recrawl.md](19-scheduled-recrawl.md) — adds `list_all_crawled_urls()` DynamoDB scan for the scheduler path

---

## Owner

Backend subagent

## Output Files

```
src/
  services/
    storage.py
```

---

## Functions

### S3 Operations

```python
def save_llms_txt(job_id: str, content: str) -> str:
    """Saves to results/{job_id}/llms.txt. Returns S3 key."""

def save_plan(job_id: str, content: str) -> str:
    """Saves markdown to results/{job_id}/plan.md. Returns S3 key."""

def get_artifact_content(job_id: str, artifact_type: str) -> str | None:
    """
    Reads artifact content from S3.
    artifact_type: 'llmsTxt' | 'analysis' | 'sitemap' | 'plan'
    Returns raw content string, or None if the artifact does not exist.
    """

def generate_download_url(s3_key: str, expiry: int = 3600) -> str:
    """Generates a presigned S3 URL for private downloads."""
```

### DynamoDB Operations

```python
def create_job(job_id: str, url: str, model: str) -> None:
    """
    Writes initial job record with overall status 'processing'
    and all 4 artifact statuses set to 'processing'.
    """

def complete_artifact(job_id: str, artifact_type: str, s3_key: str) -> None:
    """
    Marks one artifact as complete and stores its s3Key.
    artifact_type: 'llmsTxt' | 'analysis' | 'sitemap' | 'plan'
    Updates overall job status to 'complete' or 'partial' if all artifacts are now done.
    """

def fail_artifact(job_id: str, artifact_type: str, error: str) -> None:
    """
    Marks one artifact as failed and stores the error message.
    Updates overall job status to 'complete' or 'partial' if all artifacts are now done.
    """

def get_job(job_id: str) -> dict | None:
    """Reads full job record from DynamoDB. Returns None if not found."""

def get_artifact_content(job_id: str, artifact_type: str) -> str | None:
    """
    Reads the s3Key for the artifact from DynamoDB, then fetches content from S3.
    Returns None if the artifact is not complete or does not exist.
    """

def list_jobs(model_filter: str = None) -> list[dict]:
    """
    Scans DynamoDB for all jobs.
    Returns lightweight records only (jobId, status, model, url, createdAt, artifact statuses).
    Excludes artifact content.
    Sorted by createdAt descending.
    Optionally filters by model.
    """

def list_jobs_for_url(url: str) -> list[dict]:
    """
    Returns all crawl runs for a specific URL, sorted by createdAt descending.
    Queries the url-createdAt-index GSI on the jobs table — no table scan.
    """
```

### Sites Table Operations

```python
def upsert_site(
    url: str,
    job_id: str,
    s3_key: str,
    metadata: dict,
) -> None:
    """
    Creates or overwrites the canonical site record for this URL.
    Called from on_complete after every successful crawl.
    Stores the latest jobId, s3Key, SiteMetadata fields, and lastCrawledAt timestamp.
    """

def get_site(url: str) -> dict | None:
    """
    Returns the latest site record for a URL, or None if never crawled.
    """

def list_sites() -> list[dict]:
    """
    Scans the sites table — one record per unique URL ever crawled.
    Returns url, latestJobId, lastCrawledAt, status, and SiteMetadata fields.
    Used by the scheduler (list of URLs to re-crawl) and the History tab (site-level view).
    """
```

---

## DynamoDB Schemas

### `crawler-jobs` table

```json
{
  "jobId":     "string (hash key)",
  "url":       "string (GSI partition key: url-createdAt-index)",
  "model":     "string (claude)",
  "createdAt": "string (ISO 8601 UTC — GSI sort key)",
  "status":    "string (processing|complete|partial)",
  "artifacts": {
    "llmsTxt": {"status": "processing|complete|failed", "s3Key": "string", "error": "string"},
    "plan":    {"status": "processing|complete|failed", "s3Key": "string", "error": "string"}
  }
}
```

**Overall status logic** (computed inside `complete_artifact` / `fail_artifact`):
- `processing` — at least one artifact is still `processing`
- `complete` — both artifacts are `complete`
- `partial` — both are done but at least one is `failed`

**GSI: `url-createdAt-index`** — enables `list_jobs_for_url(url)` without a table scan. `ScanIndexForward=False` returns runs newest-first.

### `crawler-sites` table

One record per unique URL. Always overwritten by the latest successful crawl.

```json
{
  "url":           "string (hash key)",
  "latestJobId":   "string",
  "latestS3Key":   "string",
  "lastCrawledAt": "string (ISO 8601 UTC)",
  "model":         "string",
  "tech_stack":    ["list"],
  "audience":      "string|null",
  "tone":          "string|null",
  "business_model":"string|null",
  "integrations":  ["list"],
  "content_types": ["list"]
}
```

`SiteMetadata` fields are stored flat (not nested) so they can be used directly as Pinecone metadata without transformation.

---

## S3 Key Structure

```
results/
  {jobId}/
    llms.txt   ← crawl agent output
    plan.md    ← UI planner agent output
```

---

## Environment Variables

- `BUCKET` — S3 bucket name
- `TABLE` — DynamoDB jobs table name (`crawler-jobs`)
- `SITES_TABLE` — DynamoDB sites table name (`crawler-sites`)

---

## Acceptance Criteria

- All S3 keys follow the `results/{job_id}/...` convention
- `create_job` initializes both artifact statuses (`llmsTxt`, `plan`) to `processing`
- `complete_artifact` updates the correct artifact and recalculates overall job status
- `fail_artifact` updates the correct artifact and recalculates overall job status
- `get_artifact_content` returns `None` if the artifact status is not `complete`
- `list_jobs` excludes artifact content to keep responses lightweight
- `list_jobs_for_url` queries the GSI — does not scan the full jobs table
- `upsert_site` overwrites the previous record for the same URL — one row per URL always
- `list_sites` returns one record per unique URL (used by scheduler and History tab)
- `SiteMetadata` fields stored flat in the sites table — no nested map
- All timestamps are ISO 8601 UTC strings
- `SITES_TABLE` env var drives the sites table client — not hardcoded

---

## Tests

**File:** `tests/test_storage.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_create_job_initializes_all_artifacts` | happy | both artifact statuses start as `processing` |
| `test_complete_artifact_sets_job_complete` | happy | overall status becomes `complete` when both artifacts succeed |
| `test_one_failed_sets_job_partial` | happy | overall status becomes `partial` when one artifact fails |
| `test_get_artifact_content_not_complete_returns_none` | unhappy | returns `None` for an artifact still in `processing` |
| `test_list_jobs_for_url_returns_sorted_history` | happy | returns runs for a URL newest-first via GSI |
| `test_upsert_site_overwrites_previous` | happy | second upsert for same URL replaces the first — one row per URL |
