# Component: Lambda Handler + Routing

## How to Use This Plan

You are implementing **Component 2: Lambda Handler + Routing**. Your job is to produce `src/handler.py`. Do not implement agent logic, storage operations, or LLM calls — those are handled by other components. Stub any calls to agents and services as needed for local testing.

The same FastAPI app runs locally (via uvicorn) and on Lambda (via Mangum). No separate dev server wrapper is needed.

Dependencies:
- [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `CrawlRequest`, `ReportRequest`, `CompareRequest`, `ModelName`, `AgentType`, `ArtifactType`, `JobType`, `JobStatus`
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — must be implemented first; provides `ReportRequest`, `CompareRequest`, `JobType`
- [08-crawl-agent.md](08-crawl-agent.md) — import `CRAWL_TOOLS`
- [10-ui-planner-agent.md](10-ui-planner-agent.md) — import `UI_PLAN_TOOLS`
- [11-reporter-agent.md](11-reporter-agent.md) — import `run_reporter`
- [12-comparer-agent.md](12-comparer-agent.md) — import `run_comparer`

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — the agent factory this handler calls
- [03-storage-service.md](03-storage-service.md) — `create_job`, `get_job`, `get_artifact_content`, `list_jobs` called here
- [19-scheduled-recrawl.md](19-scheduled-recrawl.md) — adds `handle_schedule` and `handle_sqs` paths; replaces `handler = Mangum(app)` with a dispatch entrypoint

---

## Owner

Backend subagent

## Output Files

```
src/
  handler.py
```

---

## Stack

- **FastAPI** — route definitions, request validation (Pydantic models), response models
- **Mangum** — ASGI adapter that lets API Gateway invoke the FastAPI app as a Lambda function
- **uvicorn** — local development server (run directly, no wrapper file needed)

The Lambda entrypoint configured in Terraform is `handler.handler` (the Mangum-wrapped app).

---

## App Structure

```python
from fastapi import FastAPI, APIRouter, HTTPException, Query
from mangum import Mangum
import uuid

app = FastAPI()

# All routes live under /api — CloudFront routes /api/* to API Gateway,
# /* to S3 (where index.html lives). Lambda never serves the frontend.
router = APIRouter(prefix="/api")

# Lambda entrypoint — see 19-scheduled-recrawl.md for the dispatch wrapper
# that handles SQS and EventBridge events before reaching Mangum.
_mangum_handler = Mangum(app)
```

---

## Request Models

```python
class CrawlRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE

class ReportRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE

class CompareRequest(BaseModel):
    job_id_a: str
    job_id_b: str
    model: ModelName = ModelName.CLAUDE
```

All three are imported from `src/models.py` — do not redefine them here.

---

## Routes

All routes are defined on `router` (prefix `/api`) and registered with `app.include_router(router)`. There is no `GET /` — the frontend is served from S3 via CloudFront.

### `POST /api/crawl`

The single entry point for all crawling. Starts **2 agents in parallel** under the same `job_id`, each producing one artifact:

| Agent | Artifact | Saved as |
|-------|----------|----------|
| Crawl agent | llms.txt | `results/{id}/llms.txt` |
| UI planner agent | Implementation plan | `results/{id}/plan.md` |

```python
@router.post("/crawl", status_code=202)
def crawl(req: CrawlRequest):
    if req.model == "codex":
        raise HTTPException(status_code=501, detail="Codex support is not yet implemented")
    job_id = str(uuid.uuid4())
    create_job(job_id, req.url, req.model)
    _run_crawl_agents(job_id, req.url, req.model)
    return {"jobId": job_id, "status": "processing"}
```

Run both agents using `concurrent.futures.ThreadPoolExecutor` so they run in parallel within the Lambda invocation:

```python
from concurrent.futures import ThreadPoolExecutor
from src.agents.crawler import CRAWL_TOOLS
from src.agents.ui_planner import UI_PLAN_TOOLS

def _run_crawl_agents(job_id: str, url: str, model: str):
    tasks = [
        ("crawl",   CRAWL_SYSTEM_PROMPT,   CRAWL_TOOLS),
        ("ui-plan", UI_PLAN_SYSTEM_PROMPT, UI_PLAN_TOOLS),
    ]
    def run_one(agent_type, system_prompt, tools):
        agent = create_agent(model, agent_type, job_id, url, system_prompt, tools=tools)
        run_agent(agent, url)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.map(lambda t: run_one(*t), tasks)
```

FastAPI returns 422 automatically if `url` is missing from the request body.

---

### `GET /api/job`

Returns the job record including per-artifact status. Use this to poll for overall progress.

```python
@router.get("/job")
def get_job_status(id: str = Query(...)):
    job = get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
```

Response format:
```json
{
  "jobId": "abc123",
  "url": "https://example.com",
  "model": "claude",
  "createdAt": "2026-06-04T10:00:00Z",
  "status": "partial",
  "artifacts": {
    "llmsTxt": {"status": "complete", "s3Key": "results/abc123/llms.txt"},
    "plan":    {"status": "failed", "error": "Bedrock timeout"}
  }
}
```

Overall `status` values:
- `processing` — at least one artifact still running
- `complete` — both artifacts finished successfully
- `partial` — both done but at least one failed

---

### `GET /api/job/{id}/llms-txt`
### `GET /api/job/{id}/plan`

Returns the raw content of a single artifact. Returns 404 if the job does not exist or the artifact has not completed yet.

```python
@router.get("/job/{id}/llms-txt")
def get_llms_txt(id: str):
    content = get_artifact_content(id, "llmsTxt")
    if not content:
        raise HTTPException(status_code=404, detail="Artifact not ready")
    return {"jobId": id, "content": content}
```

Repeat the same pattern for `/plan`.

---

### `GET /api/jobs`

Lists all jobs. Returns lightweight records — no artifact content, just statuses.

Optional query params:
- `model` — filter by model

```python
@router.get("/jobs")
def list_all_jobs(model: str | None = None):
    return {"jobs": list_jobs(model)}
```

Sorted by `createdAt` descending.

---

### `GET /api/site`

Returns the canonical latest record for a URL, plus its full crawl history.

```python
@app.get("/site")
def get_site(url: str = Query(...)):
    site = get_site_record(url)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    history = list_jobs_for_url(url)  # queries url-createdAt-index GSI, newest first
    return {"site": site, "history": history}
```

Response includes:
- `site` — latest `SiteMetadata`, `latestJobId`, `latestS3Key`, `lastCrawledAt`
- `history` — all crawl runs for this URL (jobId, status, createdAt, artifact statuses), newest first

Used by the History tab when the user clicks a site row to see all previous crawls.

---

### `GET /api/search`

Synchronous. Embeds the query, calls Pinecone, returns ranked results with presigned S3 URLs. No job pattern.

---

### `POST /api/report`

Looks up the latest crawl for a URL and generates a structured site analysis report. Returns 202 immediately; client polls `GET /api/job`.

```python
@router.post("/report", status_code=202)
def report(req: ReportRequest):
    site = get_site(req.url)
    if not site:
        raise HTTPException(status_code=404, detail=f"No crawl found for {req.url}. Crawl the site first.")
    job_id = str(uuid.uuid4())
    create_job(job_id, req.url, req.model, JobType.REPORT)
    _run_in_thread(run_reporter, job_id, req.url, req.model)
    return {"jobId": job_id, "status": "processing"}
```

Note: The site existence check is done synchronously before creating the job so the client gets an immediate 404 rather than a job that immediately fails. `run_reporter` also checks and calls `fail_artifact` if the content is unavailable, as a safety net.

---

### `POST /api/compare`

Fetches llms.txt from two completed crawl jobs and generates a diff-focused comparison. Returns 202; client polls `GET /api/job`.

```python
@router.post("/compare", status_code=202)
def compare(req: CompareRequest):
    if req.job_id_a == req.job_id_b:
        raise HTTPException(status_code=400, detail="Cannot compare a job to itself")
    job_a = get_job(req.job_id_a)
    job_b = get_job(req.job_id_b)
    if not job_a:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id_a} not found")
    if not job_b:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id_b} not found")
    if job_a.get("status") != JobStatus.COMPLETE:
        raise HTTPException(status_code=400, detail=f"Job {req.job_id_a} is not complete")
    if job_b.get("status") != JobStatus.COMPLETE:
        raise HTTPException(status_code=400, detail=f"Job {req.job_id_b} is not complete")
    job_id = str(uuid.uuid4())
    create_job(job_id, job_a["url"], req.model, JobType.COMPARE)
    _run_in_thread(run_comparer, job_id, req.job_id_a, req.job_id_b, req.model)
    return {"jobId": job_id, "status": "processing"}
```

Validation is synchronous and returns 400/404 before any job is created — the client gets an immediate error, not a failing job.

---

### `_run_in_thread` helper

The crawl endpoint uses `ThreadPoolExecutor` to start two agents in parallel. Single-agent endpoints (report, compare) use a simpler helper:

```python
from threading import Thread

def _run_in_thread(fn, *args) -> None:
    """Starts fn(*args) in a daemon thread. Used for single-agent background jobs."""
    Thread(target=fn, args=args, daemon=True).start()
```

---

## Local Development

```bash
cd src
uv run uvicorn handler:app --reload --port 8000
```

FastAPI interactive docs available at `http://localhost:8000/docs`.

---

## Acceptance Criteria

- Single `POST /crawl` starts both agents under the same `job_id`
- Both crawl agents run in parallel via `ThreadPoolExecutor`
- `GET /job` returns per-artifact status for `llmsTxt` and `plan`
- `GET /job/{id}/llms-txt` and `GET /job/{id}/plan` return raw artifact content or 404 if not ready
- `GET /jobs` lists jobs without artifact content
- `POST /report` returns 404 if the URL has not been crawled yet
- `POST /report` returns 202 and starts the reporter in a background thread
- `POST /compare` returns 400 if both job IDs are the same
- `POST /compare` returns 404 if either job ID does not exist
- `POST /compare` returns 400 if either job is not complete
- `POST /compare` returns 202 and starts the comparer in a background thread
- Missing `url` or required fields returns 422 (FastAPI built-in validation)
- `model=codex` on `/crawl` returns 501 (until plan 18 is implemented)
- Unknown job ID returns 404
- 404 for unknown routes (FastAPI built-in)

---

## Tests

**File:** `tests/test_handler.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.
Use FastAPI's `TestClient` (wraps `httpx`).

```python
from fastapi.testclient import TestClient
from src.handler import app
client = TestClient(app)
```

| Test | Type | Verifies |
|------|------|----------|
| `test_crawl_starts_both_agents` | happy | POST /crawl returns 202 with `jobId` and invokes both `crawl` and `ui-plan` agents |
| `test_get_job_returns_artifact_statuses` | happy | GET /job returns per-artifact status for `llmsTxt` and `plan` |
| `test_get_artifact_returns_content` | happy | GET /job/{id}/llms-txt returns content when artifact is complete |
| `test_get_artifact_not_ready_returns_404` | unhappy | GET /job/{id}/plan returns 404 when not yet complete |
| `test_missing_url_returns_422` | unhappy | POST /crawl without `url` returns 422 |
| `test_report_returns_404_if_not_crawled` | unhappy | POST /report returns 404 when URL has no site record |
| `test_report_starts_reporter_and_returns_202` | happy | POST /report returns 202 with jobId when site exists |
| `test_compare_same_id_returns_400` | unhappy | POST /compare returns 400 when job_id_a == job_id_b |
| `test_compare_missing_job_returns_404` | unhappy | POST /compare returns 404 when either job ID does not exist |
| `test_compare_incomplete_job_returns_400` | unhappy | POST /compare returns 400 when either job is not complete |
| `test_compare_starts_comparer_and_returns_202` | happy | POST /compare returns 202 with jobId when both jobs are complete |
