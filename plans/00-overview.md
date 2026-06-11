# Execution Overview

> **Historical build plan.** This document (and the rest of `plans/`) captures how the system was built, phase by phase. **The build has since shipped in full** — the phase statuses below are frozen at an early point and no longer reflect reality. For the current system, see the [README](../README.md), [docs/architecture.md](../docs/architecture.md), and [docs/endpoints.md](../docs/endpoints.md).

This document defines the original build order — read it as design-intent history, not current state.

---

## Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Terraform storage — S3, DynamoDB, Secrets Manager |
| Phase 2 | ✅ Complete | All service layer files |
| Phase 3A | 🔜 Next | Foundations — amend built services before any agent work starts |
| Phase 3B | ⬜ Blocked on 3A | All agents in parallel |
| Phase 3C | ⬜ Blocked on 3B | Handler + Frontend |
| Phase 4 | ⬜ | Local end-to-end testing |
| Phase 5 | ⬜ | AWS deployment |

---

## Phase 1 — ✅ Complete

Terraform modules for S3, DynamoDB (jobs table + sites table), and Secrets Manager. Infrastructure is live in `us-east-1`.

| File | Output |
|------|--------|
| [01-terraform-storage.md](01-terraform-storage.md) | `infra/modules/s3/`, `infra/modules/dynamodb/`, `infra/modules/secrets/`, root `main.tf` |
| [15-project-tooling.md](15-project-tooling.md) *(Phase 1 section)* | `pyproject.toml`, `Makefile` |

---

## Phase 2 — ✅ Complete

All service layer files are implemented and tested. These are the shared dependencies for every agent.

| File | Output |
|------|--------|
| [04-models-constants-prompts.md](04-models-constants-prompts.md) | `src/constants.py`, `src/models.py`, `src/prompts.py` |
| [03-storage-service.md](03-storage-service.md) | `src/services/storage.py` |
| [05-embeddings-service.md](05-embeddings-service.md) | `src/services/embeddings.py` |
| [06-pinecone-service.md](06-pinecone-service.md) | `src/services/pinecone_client.py` |
| [07-agent-factory-hooks.md](07-agent-factory-hooks.md) | `src/services/llm.py`, `src/services/hooks.py`, `src/services/helpers.py` |
| [16-observability-logging.md](16-observability-logging.md) *(Part A)* | `src/services/logger.py` |

---

## Phase 3A — Foundations (run this first, blocks everything below)

**One plan. Must complete before any Phase 3B work starts.**

Amends six already-built service files to add the enums, models, prompts, storage functions, and hook branches required by the reporter and comparer agents. Also fixes a bug in `_recalculate_job_status` where the hardcoded artifact type list would prevent report/compare jobs from ever resolving to `complete`.

| File | Output |
|------|--------|
| [09-report-compare-foundations.md](09-report-compare-foundations.md) | Amends `constants.py`, `models.py`, `prompts.py`, `storage.py`, `llm.py`, `hooks.py` |

**Environment variables required (already set from Phase 1):**
```bash
export BUCKET="crawler-output-<suffix>"
export TABLE="crawler-jobs"
export SITES_TABLE="crawler-sites"
export PINECONE_API_KEY="your-pinecone-key"
export PINECONE_INDEX="your-index-name"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

Run `make lint` and `make test` after this plan to confirm no regressions.

---

## Phase 3B — Agents (all parallel after Phase 3A)

All six plans can run simultaneously — each produces only its own new files with no overlap.

| File | Output | Depends on |
|------|--------|------------|
| [08-crawl-agent.md](08-crawl-agent.md) | `src/agents/crawler.py` | Phase 2 only |
| [10-ui-planner-agent.md](10-ui-planner-agent.md) | `src/agents/ui_planner.py` | Phase 2 only |
| [13-search-endpoint.md](13-search-endpoint.md) | `src/services/search.py` | Phase 2 only |
| [11-reporter-agent.md](11-reporter-agent.md) | `src/agents/reporter.py` | Phase 3A |
| [12-comparer-agent.md](12-comparer-agent.md) | `src/agents/comparer.py` | Phase 3A |
| [18-codex-support.md](18-codex-support.md) | Amends `constants.py`, `llm.py`, `hooks.py`, `pyproject.toml` | Phase 3A |

Plans 08, 10, and 13 do not strictly require Phase 3A — but running 3A first keeps the work clean and avoids incremental re-runs of `make test`.

---

## Phase 3C — Handler + Frontend (after all of Phase 3B)

These import from every agent and must run after all of Phase 3B is complete.

| File | Output |
|------|--------|
| [02-lambda-handler.md](02-lambda-handler.md) | `src/handler.py` — all routes including `/report` and `/compare` |
| [14-frontend-ui.md](14-frontend-ui.md) | `src/index.html` — tabs: Crawl, Search, Report, Compare, History |

---

## Phase 4 — Local Testing

Set environment variables and run the local dev server. Verify every endpoint works end-to-end before touching hosting infrastructure.

```bash
make run
# → serving at http://localhost:8000
```

Open `http://localhost:8000` to test the UI, or use curl for individual endpoints.

**End-to-end test sequence:**
1. `POST /api/crawl` — crawl a site, wait for complete status
2. `GET /api/search?q=...` — verify the crawled site appears in results
3. `POST /api/report` — generate a report for the crawled URL
4. `POST /api/crawl` with the same URL using a different model (once Codex is supported)
5. `POST /api/compare` — compare the two crawl job IDs

---

## Phase 5 — AWS Deployment

Only once local testing passes.

| File | Output |
|------|--------|
| [15-project-tooling.md](15-project-tooling.md) *(Phase 5 section)* | `build.sh`, `README.md` |
| [17-terraform-hosting.md](17-terraform-hosting.md) | `infra/modules/lambda/`, `infra/modules/api_gateway/` — extends root files; includes `/report` and `/compare` routes |
| [16-observability-logging.md](16-observability-logging.md) *(Part B)* | `infra/modules/observability/` — CloudWatch dashboard |
| [19-scheduled-recrawl.md](19-scheduled-recrawl.md) | EventBridge cron + SQS queue + DLQ |
| [20-cloudfront-auth.md](20-cloudfront-auth.md) | CloudFront + S3 frontend bucket + basic auth |

```bash
make build      # packages Lambda zip
cd infra
terraform apply # adds hosting on top of existing storage resources
```

---

## Infrastructure Layout

```
infra/
  main.tf
  variables.tf
  outputs.tf
  terraform.tfvars.example   ← committed, no real values
  terraform.tfvars            ← gitignored, your real values
  modules/
    s3/
    dynamodb/
    secrets/
    lambda/         ← Phase 5
    api_gateway/    ← Phase 5
    observability/  ← Phase 5
    cloudfront/     ← Phase 5
```

---

## What Needs AWS Credentials Locally

| Service | Used in | Auth method |
|---------|---------|-------------|
| Claude (LLM) | Agent factory | Secrets Manager — `secrets/anthropic-api-key` (fetched via Lambda extension or `ANTHROPIC_API_KEY` env var locally) |
| OpenAI (Codex) | Agent factory | Secrets Manager — `secrets/openai-api-key` (fetched via extension or `OPENAI_API_KEY` env var locally) |
| Bedrock (Titan Embeddings) | Embeddings service | IAM credentials (`AWS_*` env vars) |
| S3 | Storage service | IAM credentials |
| DynamoDB | Storage service | IAM credentials |
| Pinecone | Pinecone service | `PINECONE_API_KEY` env var |
