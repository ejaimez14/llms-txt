# Component: Crawl Agent

## How to Use This Plan

You are implementing **Component 8: Crawl Agent**. Your job is to produce `src/agents/crawler.py`. The agent fetches a website, discovers its pages, and produces a structured llms.txt document via a submit tool.

This agent is one of two started in parallel by a single `POST /crawl` request. Both share the same `job_id`. Do not implement S3 uploads, DynamoDB writes, or Pinecone indexing — hooks handle all persistence automatically.

Dependencies:
- [04-models-constants-prompts.md](04-models-constants-prompts.md) — `CRAWL_SYSTEM_PROMPT` from `src/prompts.py`, `CrawlOutput` from `src/models.py`
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — `create_agent` and `run_agent` must be available

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — handler starts both crawl agents in parallel
- [10-ui-planner-agent.md](10-ui-planner-agent.md) — the other agent sharing the same `job_id`

---

## Owner

Agent subagent

## Output Files

```
src/
  agents/
    crawler.py
tests/
  test_crawler.py
```

---

## Entry Point

```python
def run_crawler(job_id: str, url: str, model: str) -> dict:
    """
    Creates agent via factory, runs it, returns the submit tool output.
    Hooks fire automatically — do not call storage functions here.
    """
```

---

## Behavior

1. Build the `CRAWL_TOOLS` list (web_search + web_fetch built-ins + `submit_crawl_results` custom tool).
2. Call `create_agent` with `tools=CRAWL_TOOLS` and `submit_tool_name="submit_crawl_results"`.
3. Call `run_agent` with a user message containing the target URL.
4. The agent uses `web_search` and `web_fetch` to discover pages, then calls `submit_crawl_results` with the completed llms.txt and site metadata.
5. The `on_complete` hook fires automatically — saves to S3, embeds, indexes to Pinecone, marks artifact complete.
6. Return the dict output from `run_agent`.

The agent drives the crawl itself — it is not a hardcoded pipeline. Page discovery depth and order are at the model's discretion.

---

## Tools

```python
from src.models import CrawlOutput

SUBMIT_TOOL = {
    "name": "submit_crawl_results",
    "description": (
        "Call this when you have finished crawling and are ready to submit. "
        "Provide the complete llms.txt content and structured site metadata."
    ),
    "input_schema": CrawlOutput.model_json_schema(),
}

CRAWL_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search"},
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]
```

`web_search` and `web_fetch` are built-in server-side tools — no implementation needed. `submit_crawl_results` is a custom tool; when the agent calls it, `run_agent` returns its input as a dict.

> **Note:** Verify the exact `type` strings for built-in tools against the Anthropic tool use docs before implementing — use the latest available version identifiers.

---

## Output Format — llms.txt Spec

The submit tool's `llms_txt` field must conform to the [llms.txt specification](https://llmstxt.org):

```markdown
# Site Name

> Brief summary of what this site is about.

Additional context: tech stack, audience, caveats.

## Core Pages

- [Home](https://example.com/): Main landing page
- [About](https://example.com/about): Company history

## Documentation

- [Getting Started](https://example.com/docs): Quickstart guide

## Optional

- [Terms of Service](https://example.com/tos): Legal terms
```

Required structure: H1 name → blockquote summary → optional body text → H2 sections with links → `## Optional` for non-critical pages.

---

## Implementation

```python
from src.models import CrawlOutput
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

SUBMIT_TOOL = {
    "name": "submit_crawl_results",
    "description": (
        "Call this when you have finished crawling and are ready to submit. "
        "Provide the complete llms.txt content and structured site metadata."
    ),
    "input_schema": CrawlOutput.model_json_schema(),
}

CRAWL_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search"},
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]


def run_crawler(job_id: str, url: str, model: str) -> dict:
    """
    Creates agent via factory, runs it, returns the submit tool output.
    Hooks fire automatically — do not call storage functions here.
    """
    agent = create_agent(
        model=model,
        agent_type="crawl",
        job_id=job_id,
        url=url,
        system_prompt=CRAWL_SYSTEM_PROMPT,
        tools=CRAWL_TOOLS,
        submit_tool_name="submit_crawl_results",
    )
    return run_agent(agent, f"Crawl this website and produce an llms.txt file: {url}")
```

---

## Acceptance Criteria

- Output conforms to the llms.txt spec (H1, blockquote, H2 sections, link format)
- `run_crawler` never imports or calls `storage`, `embed_text`, or `upsert_vector`
- Links in the output are real URLs discovered during the crawl — none invented
- Works with both `claude` and `codex` model values via the agent factory

---

## Tests

**File:** `tests/test_crawler.py`
Use `pytest`. Mock `create_agent` and `run_agent` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_crawler_passes_correct_params` | happy | `create_agent` called with `agent_type="crawl"` and `submit_tool_name="submit_crawl_results"` |
| `test_run_crawler_returns_run_agent_output` | happy | return value of `run_agent` is passed through unchanged |
| `test_crawler_no_direct_storage_calls` | happy | `crawler.py` never imports `storage`, `embed_text`, or `upsert_vector` |
