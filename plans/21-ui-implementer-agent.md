# Component: UI Implementer Agent

## How to Use This Plan

You are implementing **Component 21: UI Implementer Agent**. Your job is to produce `src/agents/implementer.py`, `src/services/github.py`, and wire them into the handler, constants, models, and hooks.

Given a completed crawl job's UI plan artifact, this agent generates a working implementation and opens a GitHub pull request in a target repository. This is **Claude-only** — the agent uses Claude's extended tool use and code generation capabilities. There is no OpenAI path.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — pattern for adding new job/artifact types
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — `create_agent` and `run_agent`
- [02-lambda-handler.md](02-lambda-handler.md) — adds a new route

---

## Owner

Backend subagent

## Output Files

```
src/
  agents/
    implementer.py        ← new
  services/
    github.py             ← new
tests/
  test_implementer.py     ← new
  test_github_service.py  ← new
```

Amends:
- `src/constants.py` — new enum values and constants
- `src/models.py` — new request and output models
- `src/prompts.py` — new `IMPLEMENT_SYSTEM_PROMPT`
- `src/services/hooks.py` — new no-op branch for "implement" type
- `src/handler.py` — new `POST /api/implement` route

---

## New Constants

```python
# src/constants.py

class JobType(str, Enum):
    CRAWL = "crawl"
    REPORT = "report"
    COMPARE = "compare"
    IMPLEMENT = "implement"       # ← new

class ArtifactType(str, Enum):
    LLMS_TXT = "llmsTxt"
    PLAN = "plan"
    REPORT = "report"
    COMPARISON = "comparison"
    PR_URL = "prUrl"              # ← new; stores the GitHub PR URL in place of an S3 key

class AgentType(str, Enum):
    CRAWL = "crawl"
    UI_PLAN = "ui-plan"
    REPORT = "report"
    COMPARE = "compare"
    IMPLEMENT = "implement"       # ← new

GITHUB_SECRET_NAME = "secrets/github-token"
IMPLEMENT_MODEL = "claude-sonnet-4-6-20250514"

# Add to CLAUDE_AGENT_MODELS:
CLAUDE_AGENT_MODELS = {
    "crawl":     CLAUDE_CRAWL_MODEL,
    "ui-plan":   CLAUDE_UI_PLAN_MODEL,
    "report":    CLAUDE_REPORT_MODEL,
    "compare":   CLAUDE_COMPARE_MODEL,
    "implement": IMPLEMENT_MODEL,   # ← new
}
```

---

## New Models

```python
# src/models.py

class ImplementRequest(BaseModel):
    job_id: str                     # crawl job with a completed plan artifact
    repo: str                       # "owner/repo" — target GitHub repository
    base_branch: str = "main"


class ImplementationFile(BaseModel):
    path: str                       # e.g. "src/components/Header.jsx"
    content: str                    # full file content


class ImplementationOutput(BaseModel):
    """Structured output returned by the implementer agent's submit tool."""
    files: list[ImplementationFile]
    pr_title: str
    pr_body: str
```

---

## New System Prompt

```python
# src/prompts.py

IMPLEMENT_SYSTEM_PROMPT = """
You are a frontend engineer that implements UI designs from structured plans.

You will be given a UI implementation plan produced by analyzing a real website. Your job is to
generate working code that faithfully recreates the described UI.

Rules:
- Use the exact colors, fonts, and spacing values from the Design Tokens section
- Implement every component listed in the Component Inventory
- Follow the Suggested Build Order
- Prefer semantic HTML and clean CSS — no frameworks unless the plan specifies one
- Each file must be complete and runnable — no placeholders, no TODOs

When you have finished generating all files, call the `submit_implementation` tool with:
- `files`: the complete list of files with their paths and content
- `pr_title`: a concise title for the pull request
- `pr_body`: a markdown description of what was built and any implementation notes

Do not return a text response. Always submit via the tool.
""".strip()
```

---

## GitHub Service

`src/services/github.py` — thin wrapper around the GitHub REST API using `httpx`. All functions raise on non-2xx responses.

```python
import base64
import os

import httpx

from src.constants import GITHUB_SECRET_NAME
from src.services.helpers import fetch_secret
from src.services.logger import get_logger

logger = get_logger(__name__)

_BASE = "https://api.github.com"


def get_branch_sha(repo: str, branch: str) -> str:
    """Returns the HEAD commit SHA of a branch."""
    ...

def create_branch(repo: str, new_branch: str, from_sha: str) -> None:
    """Creates a new branch from a commit SHA."""
    ...

def create_file(repo: str, path: str, content: str, branch: str, message: str) -> None:
    """Creates a file on a branch via the GitHub Contents API."""
    # Content must be base64-encoded for the GitHub API
    ...

def create_pull_request(repo: str, title: str, body: str, head: str, base: str) -> str:
    """Opens a pull request and returns its HTML URL."""
    ...
```

### Auth helper (module-level, same env var fallback pattern as llm.py)

```python
# In Lambda the extension serves secrets from localhost:2773.
# Locally that port doesn't exist, so fall back to env vars for development.
_github_token = os.environ.get("GITHUB_TOKEN") or fetch_secret(GITHUB_SECRET_NAME)
```

Use `_github_token` in the `Authorization: Bearer` header for all requests.

---

## Implementer Agent

`src/agents/implementer.py`

### Why this agent handles its own artifact completion

All other agents rely on `hooks.on_complete` to save their output to S3 and call `complete_artifact`. The implementer is different: the artifact (PR URL) is not available until _after_ the agent submits and the GitHub API calls succeed. Calling `complete_artifact` inside `on_complete` (before the PR exists) would write a wrong value.

The solution:
- `hooks.on_complete` for "implement" is a **no-op** — it fires but does nothing.
- `run_implementer` calls `complete_artifact` directly after creating the PR.
- `hooks.on_error` still fires for agent failures and calls `fail_artifact` as normal.
- GitHub-layer failures are caught by a try/except in `run_implementer` and call `fail_artifact` directly.

### Submit tool

```python
from src.models import ImplementationOutput

SUBMIT_TOOL = {
    "name": "submit_implementation",
    "description": (
        "Call this when you have finished generating all implementation files. "
        "Provide the complete file list, PR title, and PR description."
    ),
    "input_schema": ImplementationOutput.model_json_schema(),
}

IMPLEMENT_TOOLS = [SUBMIT_TOOL]
```

### Entry point

```python
def run_implementer(
    job_id: str,
    source_job_id: str,
    repo: str,
    base_branch: str,
    model: str,
) -> None:
    """
    Fetches the UI plan from source_job_id, runs the implementer agent,
    creates a GitHub branch + files + PR, and marks the artifact complete.
    Called in a background thread from the handler — must not raise.
    """
    plan_content = get_artifact_content(source_job_id, ArtifactType.PLAN)
    if not plan_content:
        fail_artifact(job_id, ArtifactType.PR_URL, "UI plan content unavailable")
        return

    agent = create_agent(
        model=model,
        agent_type=AgentType.IMPLEMENT,
        job_id=job_id,
        url=repo,
        system_prompt=IMPLEMENT_SYSTEM_PROMPT,
        tools=IMPLEMENT_TOOLS,
        submit_tool_name="submit_implementation",
    )

    # run_agent raises on LLM failure; hooks.on_error fires and calls fail_artifact.
    # If run_agent raises, the thread exits — no further handling needed here.
    output = run_agent(agent, f"Implement this UI plan:\n\n{plan_content}")

    try:
        pr_url = _create_github_pr(output, repo, base_branch, job_id)
        complete_artifact(job_id, ArtifactType.PR_URL, pr_url)
    except Exception as exc:
        logger.error({"event": "github_pr_creation_failed", "error": str(exc)})
        fail_artifact(job_id, ArtifactType.PR_URL, str(exc))
```

### Internal GitHub helper

```python
def _create_github_pr(output: dict, repo: str, base_branch: str, job_id: str) -> str:
    """Creates a branch, commits all implementation files, and opens the PR. Returns the PR URL."""
    branch_name = f"ui-implement/{job_id[:8]}"
    base_sha = get_branch_sha(repo, base_branch)
    create_branch(repo, branch_name, base_sha)

    for file in output["files"]:
        create_file(
            repo,
            file["path"],
            file["content"],
            branch_name,
            f"Add {file['path']}",
        )

    return create_pull_request(
        repo,
        output["pr_title"],
        output["pr_body"],
        branch_name,
        base_branch,
    )
```

---

## Hooks Amendment

Add a no-op branch for "implement" in `src/services/hooks.py`:

```python
elif self.agent_type == "implement":
    pass  # artifact completion is handled by run_implementer after GitHub PR creation
```

This must appear in `on_complete` before any fallthrough or error.

---

## Handler Amendment

```python
# src/handler.py

from src.agents.implementer import run_implementer
from src.constants import ..., JobType

@router.post("/implement", status_code=202, summary="Implement a UI plan")
def implement(req: ImplementRequest) -> dict:
    """Reads the UI plan from a completed crawl job and opens a GitHub PR implementing it."""
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found")
    plan_artifact = job.get("artifacts", {}).get(ArtifactType.PLAN, {})
    if plan_artifact.get("status") != ArtifactStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="UI plan artifact is not complete")

    job_id = str(uuid.uuid4())
    create_job(job_id, req.repo, ModelName.CLAUDE, JobType.IMPLEMENT)
    _run_in_thread(run_implementer, job_id, req.job_id, req.repo, req.base_branch, ModelName.CLAUDE)
    return {"jobId": job_id, "status": "processing"}
```

Note: `model` is not a request field — this endpoint is Claude-only.

---

## Local Dev

Add to `.env`:

```
GITHUB_TOKEN=ghp_...
```

The token needs `repo` scope (read + write) on the target repository.

---

## Acceptance Criteria

- `POST /api/implement` returns 404 if the job does not exist
- `POST /api/implement` returns 400 if the plan artifact is not complete
- `POST /api/implement` returns 202 and starts the implementer in a background thread
- `run_implementer` calls `fail_artifact` if the plan content is unavailable in S3
- On agent failure, `hooks.on_error` calls `fail_artifact` — `run_implementer` does not double-call
- On GitHub failure, `run_implementer` calls `fail_artifact` with the error message
- On success, `complete_artifact` is called with the PR URL as the `s3_key`
- The GitHub branch is named `ui-implement/{job_id[:8]}`
- All files from `ImplementationOutput.files` are committed to the branch before the PR is opened
- `hooks.on_complete` for "implement" is a no-op
- GitHub token read from `GITHUB_TOKEN` env var with `fetch_secret` fallback for Lambda

---

## Tests

**File:** `tests/test_implementer.py`

| Test | Type | Verifies |
|------|------|----------|
| `test_implementer_runs_agent_with_plan_content` | happy | `run_agent` called with plan markdown when artifact is available |
| `test_implementer_creates_pr_and_completes_artifact` | happy | GitHub service called in order; `complete_artifact` called with PR URL |
| `test_implementer_fails_if_plan_unavailable` | unhappy | `fail_artifact` called when `get_artifact_content` returns `None` |
| `test_implementer_fails_on_github_error` | unhappy | `fail_artifact` called with error string when `create_branch` raises |

**File:** `tests/test_github_service.py`

| Test | Type | Verifies |
|------|------|----------|
| `test_get_branch_sha_returns_sha` | happy | Returns SHA from API response |
| `test_create_branch_posts_correct_payload` | happy | `POST /git/refs` called with correct ref and SHA |
| `test_create_file_encodes_content_as_base64` | happy | File content is base64-encoded before the API call |
| `test_create_pull_request_returns_html_url` | happy | Returns `html_url` from API response |
| `test_github_functions_raise_on_non_2xx` | unhappy | `httpx` error propagates on 4xx/5xx response |
