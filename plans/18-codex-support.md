# Component: Codex (OpenAI) Provider Support

## How to Use This Plan

You are implementing **Component 18: Codex Support**. Your job is to add OpenAI as a second provider alongside Claude. This removes the `NotImplementedError` stub in `llm.py` and wires up a real OpenAI implementation using the same factory interface.

**All files you amend already exist.** Your changes are additive — do not remove or change Claude behavior, only extend the routing to support `model="codex"`.

Dependencies:
- [09-report-compare-foundations.md](09-report-compare-foundations.md) — must be implemented first (adds `ModelName.CODEX` to `constants.py`, which this plan builds on).

Wait — plan 09 does NOT add `ModelName.CODEX`. **This plan adds it.** Plan 09 adds `JobType`, `AgentType.REPORT`, `AgentType.COMPARE`, and related constants. This plan owns everything OpenAI-specific.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — you are amending the output of this plan
- [17-terraform-hosting.md](17-terraform-hosting.md) — add `secrets/openai-api-key` secret and `OPENAI_SECRET_NAME` Lambda env var

---

## Owner

Backend subagent

## Output Files

```
src/
  constants.py         ← add ModelName.CODEX, CODEX model IDs, OPENAI_SECRET_NAME
  services/
    llm.py             ← add OpenAI factory + run functions, remove NotImplementedError stub
    hooks.py           ← update token handling to support OpenAI usage format
pyproject.toml         ← add openai dependency
```

---

## Part A: `src/constants.py`

Add to `ModelName`:
```python
class ModelName(str, Enum):
    CLAUDE = "claude"
    CODEX  = "codex"
```

Add model ID constants in the `# --- Runtime Constants ---` block:
```python
CODEX_CRAWL_MODEL   = "gpt-4o-mini"
CODEX_UI_PLAN_MODEL = "gpt-4o"
OPENAI_SECRET_NAME  = "secrets/openai-api-key"
```

`gpt-4o-mini` for crawl (same cost-saving reasoning as Haiku for Claude) and `gpt-4o` for UI planning (same quality-first reasoning as Sonnet).

---

## Part B: `pyproject.toml`

Add `openai` to the project dependencies:
```toml
dependencies = [
    ...
    "openai>=1.0.0",
]
```

---

## Part C: `src/services/llm.py`

### 1. Add imports

```python
import json

from openai import OpenAI

from src.constants import (
    ANTHROPIC_SECRET_NAME,
    CLAUDE_COMPARE_MODEL,
    CLAUDE_CRAWL_MODEL,
    CLAUDE_MAX_OUTPUT_TOKENS,
    CLAUDE_REPORT_MODEL,
    CLAUDE_UI_PLAN_MODEL,
    CODEX_CRAWL_MODEL,
    CODEX_UI_PLAN_MODEL,
    OPENAI_SECRET_NAME,
)
from src.services.hooks import CrawlerClaudeHooks
from src.services.helpers import fetch_secret
```

### 2. Add OpenAI model map and client

```python
_OPENAI_AGENT_MODEL = {
    "crawl":   CODEX_CRAWL_MODEL,
    "ui-plan": CODEX_UI_PLAN_MODEL,
}

_openai_client = OpenAI(api_key=fetch_secret(OPENAI_SECRET_NAME))
```

Place after the Anthropic client initialization at the bottom of the file.

### 3. Update `create_agent` routing

Replace the `NotImplementedError` stub with a real call:

```python
def create_agent(...):
    if model == "claude":
        return _create_claude_agent(...)
    elif model == "codex":
        return _create_openai_agent(system_prompt, job_id, agent_type, url, model, tools, submit_tool_name)
    else:
        raise ValueError(f"Unknown model: {model!r}. Supported: 'claude', 'codex'")
```

### 4. Update `run_agent` dispatch

```python
def run_agent(agent_ctx: dict, user_content: str) -> dict | str:
    if agent_ctx["provider"] == "claude":
        return _run_claude(agent_ctx, user_content)
    if agent_ctx["provider"] == "openai":
        return _run_openai(agent_ctx, user_content)
    raise ValueError(f"Unknown provider: {agent_ctx['provider']}")
```

### 5. Add `_create_openai_agent`

```python
def _create_openai_agent(
    system_prompt: str,
    job_id: str,
    agent_type: str,
    url: str,
    model: str,
    tools: list | None = None,
    submit_tool_name: str | None = None,
) -> dict:
    model_id = _OPENAI_AGENT_MODEL.get(agent_type)
    if not model_id:
        raise ValueError(f"No OpenAI model configured for agent_type={agent_type!r}")
    hooks = CrawlerClaudeHooks(job_id, agent_type, url, model)
    return {
        "provider": "openai",
        "model_id": model_id,
        "client": _openai_client,
        "system_prompt": system_prompt,
        "hooks": hooks,
        "tools": _to_openai_tools(tools or []),
        "submit_tool_name": submit_tool_name,
    }
```

Note: `CrawlerClaudeHooks` is reused for OpenAI — the hook logic (S3 save, DynamoDB update, Pinecone upsert) is identical regardless of provider. The `model` field stored in the hooks context is `"codex"`, which flows through to DynamoDB and Pinecone metadata.

### 6. Add `_run_openai`

```python
def _run_openai(agent_ctx: dict, user_content: str) -> dict | str:
    """Makes one OpenAI API call. Returns the submit function's parsed arguments, or plain text."""
    client = agent_ctx["client"]
    hooks = agent_ctx["hooks"]
    submit_tool_name = agent_ctx.get("submit_tool_name")
    hooks.on_start()

    messages = [
        {"role": "system", "content": agent_ctx["system_prompt"]},
        {"role": "user",   "content": user_content},
    ]

    kwargs: dict = {
        "model":      agent_ctx["model_id"],
        "max_tokens": CLAUDE_MAX_OUTPUT_TOKENS,
        "messages":   messages,
    }
    if agent_ctx["tools"]:
        kwargs["tools"] = agent_ctx["tools"]

    try:
        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and submit_tool_name:
            for tool_call in choice.message.tool_calls or []:
                if tool_call.function.name == submit_tool_name:
                    result = json.loads(tool_call.function.arguments)
                    hooks.on_complete(result, response.usage)
                    return result
            raise ValueError(f"Expected submit tool call '{submit_tool_name}' not found in response")

        output = choice.message.content
        hooks.on_complete(output, response.usage)
        return output

    except Exception as exc:
        hooks.on_error(exc)
        raise
```

### 7. Add `_to_openai_tools`

Anthropic tools use `input_schema`; OpenAI uses `parameters`. This function converts agent tool definitions from Anthropic format to OpenAI format. Built-in tools (like `web_search`) don't have `input_schema` and are skipped — OpenAI does not support Anthropic's built-in tools.

```python
def _to_openai_tools(tools: list) -> list:
    """Converts Anthropic-format tool definitions to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t.get("description", ""),
                "parameters":  t["input_schema"],
            },
        }
        for t in tools
        if "input_schema" in t
    ]
```

---

## Part D: `src/services/hooks.py`

OpenAI's `usage` object uses `prompt_tokens` / `completion_tokens` instead of `input_tokens` / `output_tokens`. Update `on_complete` to handle both:

```python
input_tokens  = getattr(usage, "input_tokens",  None) or getattr(usage, "prompt_tokens",     0) or 0
output_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens",  0) or 0
```

Replace the existing two lines that extract token counts with the above.

---

## Environment Variables

- `OPENAI_SECRET_NAME` — fetched at module load via `fetch_secret`. Requires `secretsmanager:GetSecretValue` on the secret ARN in IAM. The secret is created in Phase 5 Terraform (`infra/modules/secrets/`).
- Add `OPENAI_SECRET_NAME` env var to the Lambda function in `17-terraform-hosting.md`.

For local development, the `fetch_secret` call will fail because there is no Lambda extension running. Set `OPENAI_API_KEY` directly and modify `_openai_client` initialization to check for it:

```python
_openai_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY") or fetch_secret(OPENAI_SECRET_NAME)
)
```

Apply the same pattern to the Anthropic client in `llm.py` for consistency if not already done.

---

## Acceptance Criteria

- `ModelName.CODEX = "codex"` exists in `constants.py`
- `create_agent("codex", ...)` returns an agent context with `provider="openai"` — does not raise
- `create_agent("claude", ...)` is unchanged
- `run_agent` dispatches to `_run_openai` for OpenAI contexts
- `_to_openai_tools` converts Anthropic-format tool defs to OpenAI function format
- Built-in tools without `input_schema` are filtered out by `_to_openai_tools`
- `_run_openai` extracts the submit function's JSON arguments when `finish_reason == "tool_calls"`
- `_run_openai` returns plain text when no submit tool is set
- `CrawlerClaudeHooks` is reused for Codex — no new hooks class needed
- Token counts in hooks work for both Anthropic (`input_tokens`) and OpenAI (`prompt_tokens`) usage objects
- `openai` is listed as a dependency in `pyproject.toml`
- All existing Claude tests still pass

---

## Tests

**File:** `tests/test_llm.py` — add to the existing test file.

| Test | Type | Verifies |
|------|------|----------|
| `test_create_agent_codex_returns_openai_provider` | happy | `create_agent("codex", ...)` returns context with `provider="openai"` |
| `test_run_openai_returns_structured_output` | happy | `_run_openai` parses JSON arguments and returns dict when submit tool is called |
| `test_run_openai_returns_plain_text` | happy | `_run_openai` returns message content when no submit tool is set |
| `test_to_openai_tools_converts_format` | happy | input `input_schema` becomes `parameters` in OpenAI format |
| `test_to_openai_tools_skips_builtin_tools` | happy | tools without `input_schema` are excluded from output |
