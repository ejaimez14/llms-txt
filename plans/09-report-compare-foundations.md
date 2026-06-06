# Component: Report & Compare Foundations

## How to Use This Plan

You are implementing **Component 9: Report & Compare Foundations**. Your job is to amend six already-built service files to add the enums, models, prompts, storage functions, and hook branches required by the reporter and comparer agents. Do not implement the agents themselves — those are [11-reporter-agent.md](11-reporter-agent.md) and [12-comparer-agent.md](12-comparer-agent.md).

**All six files already exist and have passing tests.** Your changes are additive — do not remove or modify existing logic, only extend it. Run `make lint` and `make test` after each file to confirm nothing broke.

Dependencies: None — all files you amend are already built.

Related plans:
- [11-reporter-agent.md](11-reporter-agent.md) — imports `AgentType.REPORT`, `ArtifactType.REPORT`, `ReportRequest`, `REPORT_SYSTEM_PROMPT`, `save_report` from what this plan adds
- [12-comparer-agent.md](12-comparer-agent.md) — imports `AgentType.COMPARE`, `ArtifactType.COMPARISON`, `CompareRequest`, `COMPARE_SYSTEM_PROMPT`, `save_comparison`
- [02-lambda-handler.md](02-lambda-handler.md) — `POST /report` and `POST /compare` routes import `ReportRequest`, `CompareRequest`, `JobType`
- [18-codex-support.md](18-codex-support.md) — runs after this plan; amends `llm.py` and `hooks.py` further

---

## Owner

Backend subagent

## Output Files

```
src/
  constants.py     ← extend enums, add model constants
  models.py        ← add ReportRequest, CompareRequest
  prompts.py       ← add REPORT_SYSTEM_PROMPT, COMPARE_SYSTEM_PROMPT
  services/
    storage.py     ← add save_report, save_comparison; fix create_job and _recalculate_job_status
    llm.py         ← add report/compare model IDs to _AGENT_MODEL
    hooks.py       ← add report/compare branches in on_complete and _artifact_key
```

---

## Part A: `src/constants.py`

Add the following to the existing file. Place `JobType` after `JobStatus`. Extend `AgentType` and `ArtifactType` with the new values. Add the new model constants in the `# --- Runtime Constants ---` block.

```python
class JobType(str, Enum):
    CRAWL   = "crawl"
    REPORT  = "report"
    COMPARE = "compare"
```

Extend `AgentType`:
```python
class AgentType(str, Enum):
    CRAWL   = "crawl"
    UI_PLAN = "ui-plan"
    REPORT  = "report"
    COMPARE = "compare"
```

Extend `ArtifactType`:
```python
class ArtifactType(str, Enum):
    LLMS_TXT    = "llmsTxt"
    PLAN        = "plan"
    REPORT      = "report"
    COMPARISON  = "comparison"
```

Add model constants (both use Sonnet — these are text-synthesis tasks, not heavy tool use):
```python
CLAUDE_REPORT_MODEL  = "claude-sonnet-4-6-20250514"
CLAUDE_COMPARE_MODEL = "claude-sonnet-4-6-20250514"
```

---

## Part B: `src/models.py`

Add two request models to the `# --- Request models ---` section:

```python
class ReportRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE


class CompareRequest(BaseModel):
    job_id_a: str
    job_id_b: str
    model: ModelName = ModelName.CLAUDE
```

No new response models are needed — the existing `JobRecord` shape works for report/compare jobs. The handler returns `{"jobId": ..., "status": "processing"}` on 202, and `GET /job` returns the full record once complete.

---

## Part C: `src/prompts.py`

Add both prompts to the existing file:

```python
REPORT_SYSTEM_PROMPT = """
You are a site analyst that produces structured reports based on llms.txt navigation files.

Given an llms.txt document for a website, produce a concise analysis in this format:

## Overview
What the site is and what it does — one paragraph.

## Target Audience
Who the site is built for, based on the content and framing in the document.

## Content Structure
The main sections and how they are organized. What kinds of pages exist.

## Notable Pages
3-5 specific pages or sections that stand out as central to the site's purpose.

## Tech & Integrations
Any technical details, frameworks, or integrations evident from the content.

## Summary Assessment
One paragraph: what makes this site distinctive, and how well the llms.txt represents the site's content.

Rules:
- Base everything strictly on what the llms.txt contains — do not speculate
- Quote specific page titles or descriptions when relevant
- Be concise — each section should be 2-5 bullet points or sentences
- If a section cannot be addressed from the available content, omit it
""".strip()


COMPARE_SYSTEM_PROMPT = """
You are an analyst comparing two llms.txt files for the same website — each produced by a different AI model.

Given two llms.txt documents labeled Model A and Model B, produce a comparison focused on differences:

## Summary
2-3 sentences on the most significant differences between the two outputs.

## Agreement
What both models included and described consistently — keep this section brief.

## Differences

### Coverage
Pages or sections that one model included but the other omitted.

### Descriptions
The same pages described differently — quote both where useful.

### Structure
How each model organized and categorized the content differently.

## Side-by-Side

| Aspect | Model A | Model B |
|--------|---------|---------|
| Total links | N | N |
| Section count | N | N |
| Dominant focus | ... | ... |

## Assessment
Which output is more complete or useful for understanding the site — and why.
Be specific and evidence-based; do not give a blanket verdict without quoting the documents.

Rules:
- Focus on differences — agreements get one short section
- Quote from the actual documents when comparing specific descriptions
- "Model A is more detailed" is not useful without citing what it includes that B does not
""".strip()
```

---

## Part D: `src/services/storage.py`

### 1. Add two S3 save functions

Place these in the `# --- S3 Operations ---` section alongside `save_llms_txt` and `save_plan`:

```python
def save_report(job_id: str, content: str) -> str:
    """Saves report markdown to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/report.md"
    _put_s3_object(s3_key, content)
    return s3_key


def save_comparison(job_id: str, content: str) -> str:
    """Saves comparison markdown to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/comparison.md"
    _put_s3_object(s3_key, content)
    return s3_key
```

### 2. Fix `create_job` to support job types

The current implementation hardcodes `llmsTxt` and `plan` artifacts. Replace with a type-driven artifact map so report and compare jobs get the correct single artifact.

Add this module-level constant (in the `# --- DynamoDB Operations ---` section, above `create_job`):

```python
_JOB_ARTIFACTS: dict[str, list[str]] = {
    JobType.CRAWL:   [ArtifactType.LLMS_TXT, ArtifactType.PLAN],
    JobType.REPORT:  [ArtifactType.REPORT],
    JobType.COMPARE: [ArtifactType.COMPARISON],
}
```

Update `create_job` signature and body:

```python
def create_job(job_id: str, url: str, model: str, job_type: str = JobType.CRAWL) -> None:
    """
    Writes the initial job record with overall status 'processing'.
    Initializes artifacts based on job_type — crawl gets llmsTxt + plan,
    report and compare each get a single artifact.
    """
    table = _jobs_table()
    processing_artifact = {"status": ArtifactStatus.PROCESSING}
    artifact_types = _JOB_ARTIFACTS.get(job_type, [])
    try:
        table.put_item(
            Item={
                "jobId":     job_id,
                "url":       url,
                "model":     model,
                "type":      job_type,
                "createdAt": _utc_now(),
                "status":    JobStatus.PROCESSING,
                "artifacts": {t: processing_artifact for t in artifact_types},
            }
        )
    except ClientError as exc:
        logger.error({"event": "create_job_failed", "error": str(exc)})
        raise
```

Add the import at the top of the file:
```python
from src.constants import ArtifactStatus, ArtifactType, JobStatus, JobType
```

### 3. Fix `_recalculate_job_status`

Remove the `_ARTIFACT_TYPES` module-level constant and fix `_recalculate_job_status` to read the job's actual artifact keys instead of the hardcoded list. This is the critical bug: a report job only has a `report` artifact, but the current code checks for `llmsTxt` and `plan`, which are always missing — so status would never update.

Remove this line from the top of the file:
```python
_ARTIFACT_TYPES = [ArtifactType.LLMS_TXT, ArtifactType.PLAN]
```

Update `_recalculate_job_status`:
```python
def _recalculate_job_status(job_id: str) -> None:
    """
    Reads the job's actual artifacts and updates overall status.
    Uses the job's own artifact map — not a hardcoded type list —
    so report and compare jobs (which have different artifacts than crawl) resolve correctly.
    """
    job = get_job(job_id)
    if job is None:
        return

    artifacts = job.get("artifacts", {})
    statuses = [artifact.get("status") for artifact in artifacts.values()]

    if any(s == ArtifactStatus.PROCESSING for s in statuses):
        return

    overall = (
        JobStatus.COMPLETE
        if all(s == ArtifactStatus.COMPLETE for s in statuses)
        else JobStatus.PARTIAL
    )

    try:
        _jobs_table().update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": overall},
        )
    except ClientError as exc:
        logger.error({"event": "recalculate_job_status_failed", "error": str(exc)})
        raise
```

---

## Part E: `src/services/llm.py`

Add `report` and `compare` to `_AGENT_MODEL`:

```python
_AGENT_MODEL = {
    "crawl":   CLAUDE_CRAWL_MODEL,
    "ui-plan": CLAUDE_UI_PLAN_MODEL,
    "report":  CLAUDE_REPORT_MODEL,
    "compare": CLAUDE_COMPARE_MODEL,
}
```

Add the new imports at the top:
```python
from src.constants import (
    ANTHROPIC_SECRET_NAME,
    CLAUDE_COMPARE_MODEL,
    CLAUDE_CRAWL_MODEL,
    CLAUDE_MAX_OUTPUT_TOKENS,
    CLAUDE_REPORT_MODEL,
    CLAUDE_UI_PLAN_MODEL,
)
```

No other changes to `llm.py`.

---

## Part F: `src/services/hooks.py`

### 1. Add imports

Add `save_report` and `save_comparison` to the storage import line:

```python
from src.services.storage import (
    complete_artifact,
    fail_artifact,
    save_comparison,
    save_llms_txt,
    save_plan,
    save_report,
    upsert_site,
)
```

### 2. Add branches to `on_complete`

Add `report` and `compare` branches after the existing `ui-plan` branch:

```python
elif self.agent_type == "report":
    s3_key = save_report(self.job_id, raw_output)
    # Report is saved to S3 only — no embedding or Pinecone indexing.

elif self.agent_type == "compare":
    s3_key = save_comparison(self.job_id, raw_output)
    # Comparison is saved to S3 only — no embedding or Pinecone indexing.
```

### 3. Update `_artifact_key`

```python
def _artifact_key(agent_type: str) -> str:
    return {
        "crawl":   "llmsTxt",
        "ui-plan": "plan",
        "report":  "report",
        "compare": "comparison",
    }[agent_type]
```

---

## S3 Key Structure

After this plan, the full key structure is:

```
results/
  {jobId}/
    llms.txt       ← crawl agent output
    plan.md        ← ui-planner agent output
    report.md      ← reporter agent output
    comparison.md  ← comparer agent output
```

---

## Acceptance Criteria

- `JobType`, `AgentType.REPORT`, `AgentType.COMPARE`, `ArtifactType.REPORT`, `ArtifactType.COMPARISON` exist in `constants.py`
- `CLAUDE_REPORT_MODEL` and `CLAUDE_COMPARE_MODEL` constants exist
- `ReportRequest` and `CompareRequest` models exist in `models.py`
- `REPORT_SYSTEM_PROMPT` and `COMPARE_SYSTEM_PROMPT` exist in `prompts.py`
- `save_report` saves to `results/{job_id}/report.md` and returns the S3 key
- `save_comparison` saves to `results/{job_id}/comparison.md` and returns the S3 key
- `create_job` accepts `job_type` param; crawl jobs get `llmsTxt`+`plan`, report jobs get `report`, compare jobs get `comparison`
- `create_job` stores `"type"` field in the DynamoDB record
- `_recalculate_job_status` iterates over `artifacts.values()` — not a hardcoded type list
- `_ARTIFACT_TYPES` module-level constant is removed from `storage.py`
- `_AGENT_MODEL` in `llm.py` includes `"report"` and `"compare"` keys
- `on_complete` in `hooks.py` handles `"report"` and `"compare"` agent types
- `_artifact_key` in `hooks.py` maps all four agent types
- All existing tests still pass after changes

---

## Tests

Update `tests/test_storage.py` — the existing `create_job` tests hardcode the artifact structure. Update them to explicitly pass `job_type=JobType.CRAWL` (no behavior change) and add:

| Test | Type | Verifies |
|------|------|----------|
| `test_create_report_job_initializes_report_artifact` | happy | report job gets only `report` artifact, not `llmsTxt`/`plan` |
| `test_create_compare_job_initializes_comparison_artifact` | happy | compare job gets only `comparison` artifact |
| `test_recalculate_resolves_report_job_on_single_artifact` | happy | status becomes `complete` when the single `report` artifact completes |
| `test_save_report_returns_correct_s3_key` | happy | `save_report` returns `results/{job_id}/report.md` |
| `test_save_comparison_returns_correct_s3_key` | happy | `save_comparison` returns `results/{job_id}/comparison.md` |
