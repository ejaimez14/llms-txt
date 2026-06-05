# Component: Lambda Handler + Routing

## How to Use This Plan

You are implementing **Component 2: Lambda Handler + Routing**. Your job is to produce `src/handler.py`. Do not implement agent logic, storage operations, or LLM calls — those are handled by other components. Stub any calls to agents and services as needed for local testing.

The same FastAPI app runs locally (via uvicorn) and on Lambda (via Mangum). No separate dev server wrapper is needed.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `CrawlRequest`, `ModelName`, `AgentType`, `ArtifactType`, and system prompts from there. [08-crawl-agent.md](08-crawl-agent.md) — import `CRAWL_TOOLS`. [10-ui-planner-agent.md](10-ui-planner-agent.md) — import `UI_PLAN_TOOLS`. Stub agent functions to test in isolation.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — the agent factory this handler calls
- [03-storage-service.md](03-storage-service.md) — `create_job`, `get_job`, `get_artifact_content` called here
- [08-crawl-agent.md](08-crawl-agent.md), [10-ui-planner-agent.md](10-ui-planner-agent.md) — both agents started from here per crawl
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

## Request Model

```python
class CrawlRequest(BaseModel):
    url: str
    model: str = "claude"
```

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

## Local Development

```bash
cd src
uv run uvicorn handler:app --reload --port 8000
```

FastAPI interactive docs available at `http://localhost:8000/docs`.

---

## Acceptance Criteria

- Single `POST /crawl` starts both agents under the same `job_id`
- Both agents run in parallel via `ThreadPoolExecutor`
- `GET /job` returns per-artifact status for `llmsTxt` and `plan`
- `GET /job/{id}/llms-txt` and `GET /job/{id}/plan` return raw artifact content or 404 if not ready
- `GET /jobs` lists jobs without artifact content
- Missing `url` returns 422 (FastAPI built-in validation)
- `model=codex` returns 501
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
