# Component: Reporter Agent

## How to Use This Plan

You are implementing **Component 11: Reporter Agent**. Your job is to produce `src/agents/reporter.py` and amend three existing files (`models.py`, `prompts.py`, `hooks.py`) to wire up the submit tool.

The reporter fetches the latest llms.txt for a URL from S3 and generates a structured analysis report via a submit tool — matching the same pattern used by crawler and ui_planner.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — must be implemented first. Provides `AgentType.REPORT`, `ArtifactType.REPORT`, `ReportRequest`, `save_report`, `get_site`.
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
    reporter.py          ← new file
  models.py              ← add ReportOutput
  prompts.py             ← update REPORT_SYSTEM_PROMPT to use submit tool
  services/
    hooks.py             ← extract report_markdown from submit tool output
tests/
  test_reporter.py       ← new file
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
6. Call `create_agent(model, AgentType.REPORT, job_id, url, REPORT_SYSTEM_PROMPT, tools=REPORT_TOOLS, submit_tool_name="submit_report")`.
7. Call `run_agent(agent, user_message)`.
8. The hook's `on_complete` extracts `report_markdown` from the submit tool output, saves it via `save_report`, and calls `complete_artifact`.
9. The hook's `on_error` calls `fail_artifact` if the LLM call fails.

---

## Part A: `src/models.py`

Add `ReportOutput` alongside the other agent output models:

```python
class ReportOutput(BaseModel):
    """Structured output returned by the reporter agent's submit tool."""

    report_markdown: str
```

---

## Part B: `src/prompts.py`

Update `REPORT_SYSTEM_PROMPT` to instruct the agent to submit via the tool instead of returning plain text. Replace the closing rules section with:

```
When you have finished your analysis, call the `submit_report` tool with:
- `report_markdown`: the complete report in the format above

Do not return a text response. Always submit via the tool.
```

---

## Part C: `src/agents/reporter.py`

```python
from src.constants import AgentType, ArtifactType
from src.models import ReportOutput
from src.prompts import REPORT_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.storage import fail_artifact, get_artifact_content, get_site

SUBMIT_TOOL = {
    "name": "submit_report",
    "description": (
        "Call this when you have finished your analysis and are ready to submit. "
        "Provide the complete report as markdown."
    ),
    "input_schema": ReportOutput.model_json_schema(),
}

REPORT_TOOLS = [SUBMIT_TOOL]


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

    agent = create_agent(
        model,
        AgentType.REPORT,
        job_id,
        url,
        REPORT_SYSTEM_PROMPT,
        tools=REPORT_TOOLS,
        submit_tool_name="submit_report",
    )
    run_agent(agent, f"Generate a report for this site:\n\n{content}")
```

---

## Part D: `src/services/hooks.py`

The `on_complete` report branch currently passes `raw_output` (a string) directly to `save_report`. Update it to extract the `report_markdown` field from the submit tool's structured output:

```python
elif self.agent_type == "report":
    output = ReportOutput.model_validate(raw_output)
    s3_key = save_report(self.job_id, output.report_markdown)
```

Add `ReportOutput` to the import from `src.models`.

---

## Acceptance Criteria

- `run_reporter` calls `fail_artifact` with a descriptive error if the site has not been crawled
- `run_reporter` calls `fail_artifact` if the llms.txt content is unavailable in S3
- On success, the agent is called with `REPORT_TOOLS` and `submit_tool_name="submit_report"`
- `ReportOutput` is defined in `models.py` and used as the tool's `input_schema`
- `hooks.py` extracts `report_markdown` from the submit output before saving to S3
- `REPORT_SYSTEM_PROMPT` instructs the agent to call `submit_report` — no plain text response
- The function does not raise — all failure paths call `fail_artifact` and return
- The hook handles saving and status updates — `run_reporter` does not touch S3 or DynamoDB directly

---

## Tests

**File:** `tests/test_reporter.py`
Use `pytest`. Mock `create_agent` and `run_agent` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_reporter_runs_agent_with_llms_txt_content` | happy | `run_agent` is called with the llms.txt content when site and content exist |
| `test_reporter_passes_submit_tool_to_agent` | happy | `create_agent` receives `submit_tool_name="submit_report"` and `tools=REPORT_TOOLS` |
| `test_reporter_fails_if_site_not_crawled` | unhappy | `fail_artifact` called with descriptive error when `get_site` returns `None` |
| `test_reporter_fails_if_content_unavailable` | unhappy | `fail_artifact` called when `get_artifact_content` returns `None` |
