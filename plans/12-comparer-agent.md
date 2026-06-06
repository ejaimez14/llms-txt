# Component: Comparer Agent

## How to Use This Plan

You are implementing **Component 12: Comparer Agent**. Your job is to produce `src/agents/comparer.py`. This agent fetches the llms.txt outputs from two crawl jobs and generates a diff-focused comparison report showing how each model interpreted the same website differently.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — must be implemented first. Provides `AgentType.COMPARE`, `ArtifactType.COMPARISON`, `CompareRequest`, `COMPARE_SYSTEM_PROMPT`, `save_comparison`.
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — `create_agent` and `run_agent` must be available.

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — calls `run_comparer` from `POST /api/compare`; handler validates that both jobs are complete and not the same ID before calling this function
- [03-storage-service.md](03-storage-service.md) — `get_job`, `get_artifact_content`, `fail_artifact` called here

---

## Owner

Backend subagent

## Output Files

```
src/
  agents/
    comparer.py
tests/
  test_comparer.py
```

---

## Entry Point

```python
def run_comparer(job_id: str, job_id_a: str, job_id_b: str, model: str) -> None:
    """
    Fetches llms.txt for both jobs and runs the comparison agent.
    Called in a background thread from the handler — must not raise.
    The handler has already validated that both jobs are complete and not the same ID.
    """
```

---

## Behavior

1. Call `get_job(job_id_a)` and `get_job(job_id_b)` to retrieve the job records (needed for model names and URLs).
2. Call `get_artifact_content(job_id_a, ArtifactType.LLMS_TXT)` and `get_artifact_content(job_id_b, ArtifactType.LLMS_TXT)`.
3. If either content is `None`, call `fail_artifact(job_id, ArtifactType.COMPARISON, "llms.txt content unavailable for one or both jobs")` and return.
4. Build the user message using `_build_compare_message(job_a, content_a, job_b, content_b)`.
5. Use `job_a["url"]` as the reference URL for the agent context.
6. Call `create_agent(model, AgentType.COMPARE, job_id, job_a["url"], COMPARE_SYSTEM_PROMPT)` — no tools, plain text output.
7. Call `run_agent(agent, user_message)`.
8. The hook's `on_complete` saves the output via `save_comparison` and calls `complete_artifact`.
9. The hook's `on_error` calls `fail_artifact` if the LLM call fails.

---

## Implementation

```python
from src.constants import AgentType, ArtifactType
from src.prompts import COMPARE_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.storage import fail_artifact, get_artifact_content, get_job


def run_comparer(job_id: str, job_id_a: str, job_id_b: str, model: str) -> None:
    """
    Fetches llms.txt for both jobs and runs the comparison agent.
    Called in a background thread from the handler — must not raise.
    """
    job_a = get_job(job_id_a)
    job_b = get_job(job_id_b)

    content_a = get_artifact_content(job_id_a, ArtifactType.LLMS_TXT)
    content_b = get_artifact_content(job_id_b, ArtifactType.LLMS_TXT)

    if not content_a or not content_b:
        fail_artifact(job_id, ArtifactType.COMPARISON, "llms.txt content unavailable for one or both jobs")
        return

    user_message = _build_compare_message(job_a, content_a, job_b, content_b)
    agent = create_agent(model, AgentType.COMPARE, job_id, job_a["url"], COMPARE_SYSTEM_PROMPT)
    run_agent(agent, user_message)


# --- Internal ---


def _build_compare_message(job_a: dict, content_a: str, job_b: dict, content_b: str) -> str:
    """Formats both llms.txt outputs into a labeled comparison message for the agent."""
    model_a = job_a.get("model", "unknown")
    model_b = job_b.get("model", "unknown")
    url_a = job_a.get("url", "")
    url_b = job_b.get("url", "")

    url_note = ""
    if url_a != url_b:
        url_note = f"\nNote: Job A is for {url_a} and Job B is for {url_b} — these are different URLs.\n"

    return (
        f"Compare these two llms.txt outputs for the same website.{url_note}\n\n"
        f"--- Model A ({model_a}) ---\n{content_a}\n\n"
        f"--- Model B ({model_b}) ---\n{content_b}"
    )
```

No tools are passed to `create_agent` — the comparer receives both documents in the user message and returns plain text. `submit_tool_name` is not set.

The `url_note` handles the edge case where two different URLs are compared — the agent is informed and adapts its analysis accordingly.

---

## Acceptance Criteria

- `run_comparer` calls `fail_artifact` if either job's llms.txt content is unavailable
- The user message passed to the agent clearly labels which content belongs to Model A and Model B
- The model name from each job record is included in the labels (not hardcoded)
- If the two jobs reference different URLs, the agent is notified via a note in the message
- `job_a["url"]` is used as the reference URL for the agent context
- No tools or submit tool are passed — plain text output is expected
- The function does not raise — all failure paths call `fail_artifact` and return
- The hook handles saving and status updates — `run_comparer` does not touch S3 or DynamoDB directly

---

## Tests

**File:** `tests/test_comparer.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock `create_agent` and `run_agent` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_comparer_runs_agent_with_both_contents` | happy | `run_agent` called with message containing both labeled llms.txt contents |
| `test_comparer_message_includes_model_names` | happy | `_build_compare_message` uses model names from job records, not hardcoded strings |
| `test_comparer_notes_different_urls` | happy | message includes a note when job_a and job_b reference different URLs |
| `test_comparer_fails_if_content_unavailable` | unhappy | `fail_artifact` called when either content is `None` |
| `test_comparer_does_not_raise_on_failure` | unhappy | function returns normally when content is missing |
