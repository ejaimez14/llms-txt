# Component: UI Implementer Agent

## How to Use This Plan

You are implementing **Component 21: UI Implementer Agent**. Your job is to produce
`src/agents/implementer.py`, `src/services/fargate.py`, `src/tasks/implementer.py`,
and wire them into the handler, constants, and models.

Given a completed crawl job's UI plan artifact, this agent generates a working frontend
implementation and opens a GitHub pull request in a target repository — entirely autonomously.
This is **Claude-only** and uses the `claude-agent-sdk` to run an iterative coding loop.
Claude writes files, iterates on them, then uses `git` and `gh` CLI via `Bash` to create the
branch, commit the implementation, and open the PR itself. Python only reads the PR URL after
the agent finishes.

### Why claude-agent-sdk instead of the agent factory

The crawl, report, and compare agents each produce one structured document in a single LLM call.
The implementer is different: it must write multiple files, read them back, revise components,
verify the output coheres, and then create a GitHub PR — a genuine end-to-end coding workflow.
The `claude-agent-sdk` gives Claude built-in `Write`, `Read`, `Edit`, `Bash`, and `Glob` tools
and manages the full multi-turn loop automatically. The agent factory's submit-tool pattern
would produce all files in a single generation step with no ability to iterate or verify.

Because the `claude-agent-sdk` runs the Claude Code CLI as a subprocess, it cannot run inside
a Lambda invocation. The handler dispatches to an **ECS Fargate task** instead of a thread.

The Fargate container must have `git` and `gh` (GitHub CLI) installed. `gh` uses the
`GITHUB_TOKEN` environment variable automatically — no explicit auth step needed.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — pattern for enum additions
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
    fargate.py            ← new
  tasks/
    __init__.py           ← new (empty)
    implementer.py        ← new (Fargate entry point)
tests/
  test_implementer.py     ← new
```

Amends:
- `src/constants.py` — new enum values and constants
- `src/models.py` — new `ImplementRequest` model
- `src/prompts.py` — new `IMPLEMENT_SYSTEM_PROMPT`
- `src/handler.py` — new `POST /api/implement` route
- `pyproject.toml` — add `claude-agent-sdk` dependency

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
    PR_URL = "prUrl"              # ← new; stores the GitHub PR URL (not an S3 key)

IMPLEMENT_MODEL = "claude-sonnet-4-6-20250514"
```

Note: No `AgentType.IMPLEMENT` — the implementer does not use the agent factory.
Note: `IMPLEMENT_MODEL` is not added to `CLAUDE_AGENT_MODELS` for the same reason.
Note: No `GITHUB_SECRET_NAME` constant — `GITHUB_TOKEN` is injected as a Fargate task
environment variable and consumed directly by the `gh` CLI; Python never reads it.

---

## New Models

```python
# src/models.py

class ImplementRequest(BaseModel):
    job_id: str          # crawl job with a completed plan artifact
    repo: str            # "owner/repo" — target GitHub repository
    base_branch: str = "main"
```

No `ImplementationOutput` or `ImplementationFile` — the agent writes files directly to disk,
creates the GitHub branch and PR via `gh` CLI, and writes the PR URL to `pr-url.txt`.

---

## New System Prompt

```python
# src/prompts.py

IMPLEMENT_SYSTEM_PROMPT = """
You are a frontend engineer that implements UI designs from structured plans.

You will be given a UI implementation plan, a target GitHub repository, and a branch name.
Your job is to implement the described UI and open a GitHub pull request — end to end.

Implementation rules:
- Use the exact colors, fonts, and spacing values from the Design Tokens section
- Implement every component listed in the Component Inventory
- Follow the Suggested Build Order
- Prefer semantic HTML and clean CSS — no frameworks unless the plan specifies one
- Each file must be complete and runnable — no placeholders, no TODOs
- Iterate: write a component, read it back, revise if needed, then move on

After writing all implementation files, use Bash to:
1. Clone the target repository into a subdirectory named `repo`
2. Create the specified branch from the base branch
3. Copy all your implementation files into the cloned repo
4. Commit and push the branch
5. Run `gh pr create` to open the pull request
6. Write the PR URL (just the URL, nothing else) to a file named `pr-url.txt`
   in the working directory (not inside the repo subdirectory)

The `GITHUB_TOKEN` environment variable is already set — `gh` will use it automatically.

Stop after writing `pr-url.txt`.
""".strip()
```

---

## No GitHub Service

There is no `src/services/github.py`. Claude creates the PR itself via `Bash` using the
`gh` CLI — Python never calls the GitHub API directly. The `GITHUB_TOKEN` environment
variable is passed to the Fargate task and consumed automatically by `gh`.

---

## Fargate Service

`src/services/fargate.py` — dispatches an ECS Fargate task to run the implementer.
This is what the handler calls instead of `_run_in_thread`.

```python
import os

import boto3

from src.services.logger import get_logger

logger = get_logger(__name__)

_ecs = boto3.client("ecs", region_name=os.environ["AWS_DEFAULT_REGION"])


def trigger_implementer_task(
    job_id: str,
    source_job_id: str,
    repo: str,
    base_branch: str,
) -> None:
    """Dispatches a Fargate task that runs run_implementer with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_TASK_DEFINITION"],
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": os.environ["ECS_SUBNET_IDS"].split(","),
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": os.environ["ECS_CONTAINER_NAME"],
                        "environment": [
                            {"name": "IMPLEMENTER_JOB_ID", "value": job_id},
                            {"name": "IMPLEMENTER_SOURCE_JOB_ID", "value": source_job_id},
                            {"name": "IMPLEMENTER_REPO", "value": repo},
                            {"name": "IMPLEMENTER_BASE_BRANCH", "value": base_branch},
                        ],
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_dispatch_failed", "error": str(exc)})
        raise
```

### Fargate task entry point

The Fargate container runs `python -m src.tasks.implementer` as its command.
Create `src/tasks/__init__.py` (empty) and `src/tasks/implementer.py`:

```python
import os
from src.agents.implementer import run_implementer
from src.constants import IMPLEMENT_MODEL

if __name__ == "__main__":
    run_implementer(
        job_id=os.environ["IMPLEMENTER_JOB_ID"],
        source_job_id=os.environ["IMPLEMENTER_SOURCE_JOB_ID"],
        repo=os.environ["IMPLEMENTER_REPO"],
        base_branch=os.environ["IMPLEMENTER_BASE_BRANCH"],
        model=IMPLEMENT_MODEL,
    )
```

---

## Implementer Agent

`src/agents/implementer.py`

### Design

1. Fetch the UI plan from S3 using `get_artifact_content`.
2. Create a temporary workspace directory.
3. Run `claude-agent-sdk`'s `query()` with `IMPLEMENT_SYSTEM_PROMPT` and a user message
   containing the plan, target repo, branch name, and base branch.
   Claude iteratively writes frontend files, then uses `Bash` to clone the repo, create the
   branch, commit all files, and open the PR via `gh pr create`. Claude writes the PR URL
   to `pr-url.txt` when done.
4. After `query()` exhausts, read `pr-url.txt` from the workspace.
5. Call `complete_artifact` with the PR URL.

Failures at any step call `fail_artifact` and do not re-raise (the task must not crash).

### Entry point

```python
import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

from src.constants import ArtifactType, IMPLEMENT_MODEL
from src.prompts import IMPLEMENT_SYSTEM_PROMPT
from src.services.logger import get_logger
from src.services.storage import complete_artifact, fail_artifact, get_artifact_content

logger = get_logger(__name__)


def run_implementer(
    job_id: str,
    source_job_id: str,
    repo: str,
    base_branch: str,
    model: str,
) -> None:
    """
    Fetches the UI plan from source_job_id, runs the Claude Code agent to generate
    frontend files and open a GitHub PR, then marks the artifact complete.
    Called as the Fargate task entrypoint — must not raise.
    """
    plan_content = get_artifact_content(source_job_id, ArtifactType.PLAN)
    if not plan_content:
        fail_artifact(job_id, ArtifactType.PR_URL, "UI plan content unavailable")
        return

    try:
        asyncio.run(_run_agent(job_id, plan_content, repo, base_branch, model))
    except Exception as exc:
        logger.error({"event": "implementer_failed", "error": str(exc)})
        fail_artifact(job_id, ArtifactType.PR_URL, str(exc))
```

### Internal functions

```python
async def _run_agent(
    job_id: str,
    plan_content: str,
    repo: str,
    base_branch: str,
    model: str,
) -> None:
    """Runs the claude-agent-sdk loop, reads the PR URL from pr-url.txt, and completes the artifact."""
    branch_name = f"ui-implement/{job_id[:8]}"
    prompt = _build_prompt(plan_content, repo, branch_name, base_branch)

    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=model,
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
            max_turns=80,
        )
        await asyncio.wait_for(
            _exhaust(query(prompt=prompt, options=options)),
            timeout=3600,  # 1-hour hard ceiling
        )

        pr_url = Path(workspace, "pr-url.txt").read_text().strip()
        if not pr_url.startswith("https://github.com"):
            raise ValueError(f"Unexpected pr-url.txt content: {pr_url!r}")
        complete_artifact(job_id, ArtifactType.PR_URL, pr_url)


async def _exhaust(gen) -> None:
    """Drains an async generator, logging each message type."""
    async for message in gen:
        logger.info({"event": "implementer_message", "type": type(message).__name__})


def _build_prompt(plan_content: str, repo: str, branch_name: str, base_branch: str) -> str:
    """Builds the user-facing prompt with task-specific context for the implementer agent."""
    return (
        f"Repository: {repo}\n"
        f"Base branch: {base_branch}\n"
        f"Implementation branch: {branch_name}\n"
        f"The GITHUB_TOKEN environment variable is set — gh will use it automatically.\n\n"
        f"Implement this UI plan:\n\n{plan_content}"
    )
```

---

## Handler Amendment

```python
# src/handler.py

from src.models import ..., ImplementRequest
from src.constants import ..., ArtifactStatus, ArtifactType, JobType
from src.services.fargate import trigger_implementer_task
from src.services.storage import ..., get_artifact_content

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
    trigger_implementer_task(job_id, req.job_id, req.repo, req.base_branch)
    return {"jobId": job_id, "status": "processing"}
```

Note: `model` is not a request field — this endpoint is Claude-only. `IMPLEMENT_MODEL` is
used directly by the Fargate task entry point.

---

## No Hooks Amendment

The implementer does not use the agent factory, so `hooks.py` requires **no changes**.
Artifact lifecycle is managed directly by `run_implementer` and `_run_agent`.

---

## pyproject.toml Amendment

Add to `[project] dependencies`:

```toml
"claude-agent-sdk>=0.1",
```

---

## Environment Variables

Add to `.env` for local testing. In Lambda/Fargate, these come from Secrets Manager or
ECS task definition environment configuration.

```
GITHUB_TOKEN=ghp_...

# ECS — only needed by the Lambda handler, not the Fargate task itself
ECS_CLUSTER=llms-txt-cluster
ECS_TASK_DEFINITION=llms-txt-implementer
ECS_SUBNET_IDS=subnet-abc123,subnet-def456
ECS_CONTAINER_NAME=implementer
```

The GitHub token needs `repo` scope (read + write) on the target repository.

---

## Acceptance Criteria

- `POST /api/implement` returns 404 if the source job does not exist
- `POST /api/implement` returns 400 if the plan artifact is not complete
- `POST /api/implement` returns 202 and dispatches a Fargate task
- `run_implementer` calls `fail_artifact` if the plan content is unavailable in S3
- On agent failure, `run_implementer` catches the exception, logs it, and calls `fail_artifact`
- On `pr-url.txt` missing, unreadable, or containing an unexpected value, `run_implementer` catches, logs, and calls `fail_artifact`
- On success, `complete_artifact` is called with the GitHub PR URL read from `pr-url.txt`
- Agent is capped at `max_turns=80` and a 1-hour `asyncio.wait_for` timeout; either limit hitting results in `fail_artifact`
- The GitHub branch is named `ui-implement/{job_id[:8]}`
- The user prompt includes the repo, branch name, and base branch before the plan content
- `claude-agent-sdk` is listed as a project dependency in `pyproject.toml`
- The Fargate task entry point reads all parameters from environment variables
- The Fargate container image must have `git` and `gh` (GitHub CLI) installed

---

## Tests

**File:** `tests/test_implementer.py`

Mock `claude_agent_sdk.query` to return an async generator that yields nothing — the agent
is considered done when the generator exhausts. Use `monkeypatch` and `tmp_path` to control
`TemporaryDirectory` so tests can pre-populate `pr-url.txt` in a known location.
Mock all `src.services.storage` calls.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_implementer_fails_if_plan_unavailable` | unhappy | `fail_artifact` called when `get_artifact_content` returns `None`; `query` not called |
| `test_run_implementer_runs_agent_with_plan_content` | happy | `query` called with prompt containing the repo, branch, and plan content |
| `test_run_implementer_reads_pr_url_and_completes_artifact` | happy | `pr-url.txt` is read; `complete_artifact` called with its contents |
| `test_run_implementer_fails_if_pr_url_missing` | unhappy | `fail_artifact` called when `pr-url.txt` does not exist after agent completes |
| `test_run_implementer_fails_on_timeout` | unhappy | `fail_artifact` called when `asyncio.wait_for` raises `TimeoutError` |
