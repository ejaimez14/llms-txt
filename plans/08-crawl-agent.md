# Component: Crawl Agent

## How to Use This Plan

You are implementing **Component 8: Crawl Agent**. Your job is to produce `src/agents/crawler.py`. The agent fetches a website, discovers its pages, and produces output in the **llms.txt format**.

This agent is one of **2 agents started in parallel** by a single `POST /crawl` request. Both share the same `job_id`. This agent's output is the `ArtifactType.LLMS_TXT` artifact. Do not implement S3 uploads, DynamoDB writes, or Pinecone indexing — the SDK hooks from [07-agent-factory-hooks.md](07-agent-factory-hooks.md) handle all of that automatically.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `CRAWL_SYSTEM_PROMPT` from `src/prompts.py`. [07-agent-factory-hooks.md](07-agent-factory-hooks.md) must be available (or stubbed).

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — factory creates the agent; hooks call `complete_artifact(ArtifactType.LLMS_TXT, ...)`
- [02-lambda-handler.md](02-lambda-handler.md) — handler starts both agents in parallel

---

## Owner

Agent subagent

## Output Files

```
src/
  agents/
    crawler.py
```

---

## Entry Point

```python
from src.constants import ModelName
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

def run_crawler(job_id: str, url: str, model: ModelName) -> str:
    """
    Creates agent via factory, runs it, returns the final output.
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

## Agent Behavior

The model drives the crawl itself using tools — it is not a hardcoded pipeline. The agent:

1. Uses `web_fetch` to retrieve the starting URL
2. Follows discovered links using `web_fetch` or `web_search`, going 1–2 levels deep at its own discretion
3. Once it has gathered enough page data, produces the final llms.txt-format output as its `end_turn` response
4. The `on_complete` hook fires automatically — saves to S3, embeds, indexes to Pinecone, marks artifact complete

The agent does **not** call `save_llms_txt`, `complete_job`, `embed_text`, or `upsert_vector`. Hooks handle all of that.

---

## Tools

Three tools in `crawler.py`: two built-in server-side tools (no implementation needed) and one custom submit tool that enforces structured output.

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
    {"type": "web_fetch_20250305",  "name": "web_fetch"},
    SUBMIT_TOOL,
]
```

- `web_search` / `web_fetch` — built-in, run server-side, transparent to your code
- `submit_crawl_results` — custom; Claude calls this at the end, returning a `CrawlOutput`-shaped dict guaranteed to match the Pydantic schema

> **Note:** Verify the exact `type` strings against the [Anthropic tool use docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool) before implementing. Use the latest available version.

---

## Output Format — llms.txt Spec

The crawler output must conform to the [llms.txt specification](https://llmstxt.org). The format is markdown:

```markdown
# Site Name

> Brief summary of what this site is about. Key information
> necessary for understanding the rest of the file.

Additional context and important notes about the site.
Things like what technology it uses, who it's for,
any caveats or important details.

## Core Pages

- [Home](https://example.com/): Main landing page with product overview
- [About](https://example.com/about): Company history and mission

## Documentation

- [Getting Started](https://example.com/docs/start): Quickstart guide

## Optional

- [Terms of Service](https://example.com/tos): Legal terms
- [Privacy Policy](https://example.com/privacy): Data handling policies
```

Required structure:
1. **H1** — site/project name (required)
2. **Blockquote** — short summary with key info (strongly recommended)
3. **Body text** — additional context, notes, caveats (optional)
4. **H2 sections** — categories grouping related links
5. Each link: `- [Page Title](URL): Brief description`
6. **## Optional** section at the end for less critical pages (legal, privacy, careers)

---

## LLM System Prompt

Instruct the LLM to:
- Identify the site name for the H1
- Write a concise blockquote summary capturing the site's purpose
- Add important context as body text (tech stack, audience, caveats)
- Categorize all discovered pages into logical H2 sections
- Write a brief, useful description for each link
- Place less critical pages under `## Optional`
- Follow the exact llms.txt markdown format — no deviations

The **same prompt** is sent to both Claude and Codex. The goal is to compare how each model handles the same task.

---

## Acceptance Criteria

- Output conforms to the llms.txt spec (H1, blockquote, H2 sections, link format)
- Agent does not call storage, DynamoDB, or Pinecone directly
- Links in the output are real, valid URLs discovered during the crawl
- Handles pages that return non-200 status codes (skip them)
- Truncates page content to stay within context window limits
- Works with both `claude` and `codex` model values via the agent factory

---

## Tests

**File:** `tests/test_crawler.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_crawler_passes_correct_params` | happy | calls `create_agent` with `agent_type="crawl"` and `submit_tool_name="submit_crawl_results"` |
| `test_run_crawler_returns_run_agent_output` | happy | return value of `run_agent` is passed through unchanged |
| `test_crawl_no_direct_storage_calls` | happy | `crawler.py` never imports `storage`, `embed_text`, or `upsert_vector` |
