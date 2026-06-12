# API reference

All routes are served under the `/api` prefix. Every request goes through CloudFront basic auth and the API Gateway `x-api-key`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/crawl` | Start a crawl — produces the llms.txt + UI plan |
| GET | `/api/job?id=<jobId>` | Poll one job's status and per-artifact state |
| GET | `/api/job/{id}/llms-txt` | Fetch the llms.txt artifact |
| GET | `/api/job/{id}/plan` | Fetch the UI plan artifact |
| GET | `/api/job/{id}/report` | Fetch the report artifact |
| GET | `/api/job/{id}/comparison` | Fetch the comparison artifact |
| GET | `/api/job/{id}/pr-url` | Fetch an implement job's PR URL + preview URL |
| GET | `/api/jobs?model=<claude\|openai>` | List all jobs (the `model` filter is optional) |
| GET | `/api/site?url=<url>` | Latest site record + crawl history for a URL |
| GET | `/api/search?q=<query>` | Semantic search over crawled content (synchronous) |
| POST | `/api/report` | Generate a report on **both** models for a crawled URL |
| POST | `/api/compare` | Compare the latest report from each model for a URL |
| POST | `/api/implement` | Open a GitHub PR for a UI plan and publish a live preview |

## Request bodies

- **`POST /api/crawl`** — `{ "url": "...", "model"?: "claude" | "openai" }` (defaults to `claude`).
- **`POST /api/report`** — `{ "url": "..." }`. Fires both models and returns `{ "jobIdClaude", "jobIdOpenai", "status" }`. `404` if the URL was never crawled.
- **`POST /api/compare`** — `{ "url": "...", "model"?: "claude" | "openai" }`. Auto-finds the latest completed report for each model, then runs the comparison on the chosen `model` (default `claude`). Returns `{ "jobId", "status" }`, or `404` naming the model whose report is missing.
- **`POST /api/implement`** — `{ "job_id": "<crawl job with a completed plan>" }`. Returns `{ "jobId", "status" }`.

## Responses & status codes

- The four `POST` endpoints return **`202 Accepted`** with `"status": "processing"` and a job id (`jobId`, or `jobIdClaude`/`jobIdOpenai` for `/report`). The work runs in the background — poll `GET /api/job`.
- `GET` endpoints return **`200`**; a **`404`** means either the job/site doesn't exist *or* the artifact isn't ready yet (keep polling).
- `POST /api/implement` also returns **`400`** if the referenced crawl's UI plan isn't complete.

Example response shapes:

```jsonc
// GET /api/job?id=<jobId>
{ "jobId": "...", "url": "...", "model": "claude", "createdAt": "...",
  "status": "processing | complete | partial | failed",
  "artifacts": { "llmsTxt": { "status": "complete" }, "plan": { "status": "processing" } } }

// GET /api/job/{id}/llms-txt   (also /plan, /report, /comparison)
{ "jobId": "...", "content": "# ..." }

// GET /api/jobs   — lightweight: artifact status only, no content
{ "jobs": [ { "jobId": "...", "url": "...", "model": "...", "status": "...", "artifacts": { } } ] }

// GET /api/search?q=...
{ "query": "...", "results": [ { "jobId": "...", "score": 0.19, "url": "...",
  "s3Key": "...", "model": "claude", "downloadUrl": "https://..." } ] }
```

## Implement previews

`POST /api/implement` does two things: it opens a GitHub PR implementing the UI plan, and it publishes the built UI to `s3://<frontend-bucket>/experimental/<jobId>/`. Because CloudFront serves that bucket, the result is live at `<cloudfront-url>/experimental/<jobId>/` (behind the same basic auth). Both links come back from `GET /api/job/{id}/pr-url` as `prUrl` and `previewUrl`.

## Site metadata

Each crawl extracts structured, search-filterable metadata stored on the site record (`GET /api/site`): `site_category`, `primary_topics`, `tech_stack`, `integrations`, `business_model`, `target_audience`, `content_tone`, `has_public_api`, and `languages`.

Full request/response schemas live in the Pydantic models in [`src/models.py`](../src/models.py).
