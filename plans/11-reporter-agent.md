# Component: Reporter Agent

## How to Use This Plan

You are implementing **Component 11: Reporter Agent**. Your job is to produce `src/agents/reporter.py`. This agent fetches the latest llms.txt for a URL from S3 and generates a structured analysis report.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — must be implemented first. Provides `AgentType.REPORT`, `ArtifactType.REPORT`, `ReportRequest`, `REPORT_SYSTEM_PROMPT`, `save_report`, `get_site`.
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — `create_agent` and `run_agent` must be available.

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — calls `run_reporter` from `POST /api/report`
- [03-storage-service.md](03-storage-service.md) — `get_site`, `get_artifact_content`, `fail_artifact` called here

---

## Owner

Backend subagent

## Output Files

```
src/
  agents/
    reporter.py
tests/
  test_reporter.py
```

---

## Entry Point

```python
def run_reporter(job_id: str, url: str, model: str) -> None:
    """
    Fetches the latest llms.txt for url and runs the report agent.
    Called in a background thread from the handler — must not raise.
    Calls fail_artifact directly for pre-flight failures; relies on
    hooks.on_error for failures that occur during agent execution.
    """
```

---

## Behavior

1. Call `get_site(url)` to look up the canonical site record.
2. If no site record exists, call `fail_artifact(job_id, ArtifactType.REPORT, f"No crawl found for {url}")` and return.
3. Call `get_artifact_content(site["latestJobId"], ArtifactType.LLMS_TXT)` to fetch the llms.txt content.
4. If content is `None`, call `fail_artifact(job_id, ArtifactType.REPORT, "llms.txt content unavailable")` and return.
5. Build the user message: `f"Generate a report for this site:\n\n{content}"`
6. Call `create_agent(model, AgentType.REPORT, job_id, url, REPORT_SYSTEM_PROMPT)` — no tools, no submit tool (plain text output).
7. Call `run_agent(agent, user_message)`.
8. The hook's `on_complete` saves the output via `save_report` and calls `complete_artifact`.
9. The hook's `on_error` calls `fail_artifact` if the LLM call fails.

---

## Implementation

```python
from src.constants import AgentType, ArtifactType
from src.prompts import REPORT_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.storage import fail_artifact, get_artifact_content, get_site


def run_reporter(job_id: str, url: str, model: str) -> None:
    """
    Fetches the latest llms.txt for url and runs the report agent.
    Called in a background thread from the handler — must not raise.
    """
    site = get_site(url)
    if not site:
        fail_artifact(job_id, ArtifactType.REPORT, f"No crawl found for {url}")
        return

    content = get_artifact_content(site["latestJobId"], ArtifactType.LLMS_TXT)
    if not content:
        fail_artifact(job_id, ArtifactType.REPORT, "llms.txt content unavailable")
        return

    agent = create_agent(model, AgentType.REPORT, job_id, url, REPORT_SYSTEM_PROMPT)
    run_agent(agent, f"Generate a report for this site:\n\n{content}")
```

No tools are passed to `create_agent` — the reporter receives content directly in the user message and returns plain text. `submit_tool_name` is not set, so `run_agent` returns the text and the hook saves it.

---

## Acceptance Criteria

- `run_reporter` calls `fail_artifact` with a descriptive error if the site has not been crawled
- `run_reporter` calls `fail_artifact` if the llms.txt content is unavailable in S3
- On success, the agent is called with the full llms.txt content and `REPORT_SYSTEM_PROMPT`
- No tools or submit tool are passed — plain text output is expected
- The function does not raise — all failure paths call `fail_artifact` and return
- The hook handles saving and status updates — `run_reporter` does not touch S3 or DynamoDB directly

---

## Tests

**File:** `tests/test_reporter.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock `create_agent` and `run_agent` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_reporter_runs_agent_with_llms_txt_content` | happy | `run_agent` is called with the llms.txt content when site and content exist |
| `test_reporter_fails_if_site_not_crawled` | unhappy | `fail_artifact` called with descriptive error when `get_site` returns `None` |
| `test_reporter_fails_if_content_unavailable` | unhappy | `fail_artifact` called when `get_artifact_content` returns `None` |
| `test_reporter_does_not_raise_on_preflight_failure` | unhappy | function returns normally (no exception) when site is missing |
