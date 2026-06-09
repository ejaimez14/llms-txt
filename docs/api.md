# API Reference

Base URL: the `api_url` output from `terraform output`, or `http://localhost:8000` locally.

Interactive docs (request/response schemas, try-it): append `/docs` to the base URL.

---

## Endpoints

| Method | Path | What it does | Returns |
|---|---|---|---|
| `POST` | `/api/crawl` | Start a crawl job for a URL | `{ jobId, status: "processing" }` |
| `GET` | `/api/job` | Get job status by `?id=` | Job record with per-artifact statuses |
| `GET` | `/api/job/{id}/llms-txt` | Get the raw `llms.txt` content | `{ jobId, content }` |
| `GET` | `/api/job/{id}/plan` | Get the UI implementation plan | `{ jobId, content }` |
| `GET` | `/api/job/{id}/report` | Get the site analysis report | `{ jobId, content }` |
| `GET` | `/api/job/{id}/comparison` | Get the comparison between two jobs | `{ jobId, content }` |
| `GET` | `/api/jobs` | List all jobs (optional `?model=` filter) | `{ jobs: [...] }` |
| `GET` | `/api/site` | Get latest site record + crawl history by `?url=` | `{ site, history }` |
| `GET` | `/api/search` | Semantic search across all indexed sites by `?q=` | `{ query, results }` |
| `POST` | `/api/report` | Generate a site analysis report for a crawled URL | `{ jobId, status: "processing" }` |
| `POST` | `/api/compare` | Compare two completed crawl jobs | `{ jobId, status: "processing" }` |
| `POST` | `/api/implement` | Open a GitHub PR implementing the UI plan for a job | `{ jobId, status: "processing" }` |

---

## Async jobs

`POST /crawl`, `/report`, `/compare`, and `/implement` return immediately with a `jobId`. Poll `GET /api/job?id={jobId}` until `status` is `"complete"` or `"partial"`, then fetch the artifact content via the relevant `GET` endpoint.

## Models

Pass `"model": "claude"` (default) or `"model": "openai"` on crawl/report/compare requests to choose which LLM runs the agent.
