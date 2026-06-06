# Component: Agent Factory + SDK Hooks

## How to Use This Plan

You are implementing **Component 7: Agent Factory + SDK Hooks**. This is the most critical shared component. Your job is to produce `src/services/llm.py` and `src/services/hooks.py`.

All persistence (S3, DynamoDB, Pinecone) happens in hooks — never in agent code or handler code. The factory creates agents with hooks pre-attached so agents stay focused on their task.

**Currently implemented:** Claude via the direct Anthropic API (`anthropic.Anthropic()`). Auth via `ANTHROPIC_API_KEY` env var.
**Codex/future providers:** the factory is structured so adding a new provider means adding one `elif` branch and a new hooks implementation. See the extensibility notes below.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `AgentType` and `ModelName` enums from there. Designed alongside [03-storage-service.md](03-storage-service.md), [05-embeddings-service.md](05-embeddings-service.md), and [06-pinecone-service.md](06-pinecone-service.md), but can be built and stubbed independently.

Related plans:
- [03-storage-service.md](03-storage-service.md) — hooks call `save_*`, `complete_job`, `fail_job`
- [05-embeddings-service.md](05-embeddings-service.md) — crawl completion hook calls `embed_text`
- [06-pinecone-service.md](06-pinecone-service.md) — crawl completion hook calls `upsert_vector`
- [16-observability-logging.md](16-observability-logging.md) — hooks call the structured logger

---

## Owner

Backend subagent

## Output Files

```
src/
  services/
    llm.py
    hooks.py
```

---

## Part A: Agent Factory (`src/services/llm.py`)

Creates and configures agents using the correct provider based on the `model` parameter, with lifecycle hooks pre-attached.

### Functions

```python
def create_agent(
    model: str,
    agent_type: str,
    job_id: str,
    url: str,
    system_prompt: str,
    tools: list = None,
    submit_tool_name: str = None,
):
    """
    Creates an agent with hooks pre-attached.
    model: 'claude' (only supported value currently)
    agent_type: 'crawl' | 'ui-plan'
    tools: list of tool dicts — built-in (web_search, web_fetch) + the custom submit tool.
    submit_tool_name: name of the custom tool Claude calls to return structured output
                      (e.g. 'submit_crawl_results'). When set, run_agent returns block.input
                      instead of text. When None, falls back to returning plain text.
    Returns an agent context dict ready to pass to run_agent().
    Raises NotImplementedError for known-but-unimplemented models (e.g. 'codex').
    Raises ValueError for completely unknown model values.
    """

def run_agent(agent_ctx: dict, user_content: str) -> dict | str:
    """
    Sends the user content to the model with tools attached.
    If submit_tool_name is set: returns block.input dict when Claude calls the submit tool.
    Otherwise: returns plain text from stop_reason == 'end_turn'.
    Dispatches to the correct run function based on agent_ctx['provider'].
    """
```

### Model Routing

```python
def create_agent(model, agent_type, job_id, url, system_prompt, tools=None, submit_tool_name=None):
    if model == 'claude':
        return _create_claude_agent(
            system_prompt, job_id, agent_type, url, model, tools, submit_tool_name
        )
    elif model == 'codex':
        # TO ADD CODEX: implement _create_openai_agent() in this file using the openai SDK,
        # add CrawlerOpenAIHooks to hooks.py, add 'openai' to pyproject.toml,
        # and add OPENAI_API_KEY to Lambda env vars in 17-terraform-hosting.md.
        raise NotImplementedError("Codex support is not yet implemented")
    else:
        raise ValueError(f"Unknown model: {model!r}. Supported: 'claude'")
```

### Claude via Direct Anthropic API

Use `anthropic.Anthropic()`. Both the Anthropic and Pinecone API keys are fetched at module load time via the [AWS Parameters and Secrets Lambda Extension](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets_lambda.html). The extension runs a local sidecar on `localhost:2773` that caches secrets from Secrets Manager — fast enough for module-level initialization, with automatic rotation support. The Lambda layer ARN is added in Phase 5 (`infra/modules/lambda/`).

```python
import json
import os
import urllib.request
from anthropic import Anthropic
from src.constants import ANTHROPIC_SECRET_NAME, CLAUDE_CRAWL_MODEL, CLAUDE_UI_PLAN_MODEL

_AGENT_MODEL = {
    "crawl":   CLAUDE_CRAWL_MODEL,
    "ui-plan": CLAUDE_UI_PLAN_MODEL,
}

def _fetch_secret(secret_name: str) -> str:
    """Fetches a secret value from the Lambda Parameters and Secrets Extension (localhost cache)."""
    url = f"http://localhost:2773/secretsmanager/get?secretId={secret_name}"
    req = urllib.request.Request(url, headers={"X-Aws-Parameters-Secrets-Token": os.environ["AWS_SESSION_TOKEN"]})
    with urllib.request.urlopen(req) as resp:
        return json.loads(json.loads(resp.read())["SecretString"])["value"]

_anthropic_client = Anthropic(api_key=_fetch_secret(ANTHROPIC_SECRET_NAME))

def _create_claude_agent(system_prompt, job_id, agent_type, url, model, tools=None, submit_tool_name=None):
    model_id = _AGENT_MODEL.get(agent_type)
    if not model_id:
        raise ValueError(f"No Claude model configured for agent_type={agent_type!r}")
    hooks = CrawlerClaudeHooks(job_id, agent_type, url, model)
    return {
        "provider": "claude",
        "model_id": model_id,
        "client": _anthropic_client,
        "system_prompt": system_prompt,
        "hooks": hooks,
        "tools": tools or [],
        "submit_tool_name": submit_tool_name,
    }
```

The same `_fetch_secret` pattern is used in `pinecone_client.py` for the Pinecone API key.

def run_agent(agent_ctx, user_content):
    if agent_ctx["provider"] == "claude":
        return _run_claude(agent_ctx, user_content)
    # Add new providers here
    raise ValueError(f"Unknown provider: {agent_ctx['provider']}")

def _run_claude(agent_ctx, user_content):
    """
    Sends one request with tools attached.
    Built-in tools (web_search, web_fetch) run server-side and are transparent.
    The submit tool (e.g. submit_crawl_results) appears as stop_reason='tool_use' —
    we extract block.input as the structured output and pass it to hooks.on_complete.
    """
    client = agent_ctx["client"]
    hooks = agent_ctx["hooks"]
    submit_tool_name = agent_ctx.get("submit_tool_name")
    hooks.on_start()

    messages = [{"role": "user", "content": user_content}]

    try:
        response = client.messages.create(
            model=agent_ctx["model_id"],
            max_tokens=4096,
            system=agent_ctx["system_prompt"],
            tools=agent_ctx["tools"],
            messages=messages,
        )

        if response.stop_reason == "tool_use" and submit_tool_name:
            for block in response.content:
                if block.type == "tool_use" and block.name == submit_tool_name:
                    hooks.on_complete(block.input, response.usage)
                    return block.input
            raise ValueError(f"Expected submit tool call '{submit_tool_name}' not found in response")

        # Fallback for agents without a submit tool
        output = next(b.text for b in response.content if hasattr(b, "text"))
        hooks.on_complete(output, response.usage)
        return output

    except Exception as e:
        hooks.on_error(e)
        raise
```

---

## Part B: Lifecycle Hooks (`src/services/hooks.py`)

Shared hook implementations. All persistence and observability lives here — agents and the handler never touch S3, DynamoDB, or Pinecone directly.

### Base Class (for extensibility)

Define a base class so future providers follow the same interface:

```python
class AgentHooks:
    """Base class. Implement one subclass per provider."""
    def on_start(self): ...
    def on_complete(self, output: dict | str, usage=None): ...
    def on_error(self, error: Exception): ...
```

### Claude Hooks

```python
class CrawlerClaudeHooks(AgentHooks):
    def __init__(self, job_id: str, agent_type: str, url: str, model: str):
        self.job_id = job_id
        self.agent_type = agent_type
        self.url = url
        self.model = model
        self._start_time = None

    def on_start(self):
        self._start_time = time.time()
        log_job_event(logger, f"{self.agent_type}_started",
                      self.job_id, url=self.url, model=self.model)

    def on_complete(self, raw_output: dict | str, usage=None):
        from src.models import CrawlOutput, UIPlanOutput
        duration_ms = int((time.time() - self._start_time) * 1000)

        if self.agent_type == 'crawl':
            output = CrawlOutput.model_validate(raw_output)
            s3_key = save_llms_txt(self.job_id, output.llms_txt)
            metadata = output.metadata.model_dump()  # tech_stack, audience, tone, etc.

            # Pinecone: vector ID is URL hash — overwrites the previous vector for this site.
            # Using jobId would accumulate one vector per run; URL keeps exactly one per site.
            vector = embed_text(output.llms_txt)
            upsert_vector(_url_vector_id(self.url), vector, {
                'url': self.url,
                's3Key': s3_key,
                'model': self.model,
                'artifact': 'crawl',
                **metadata,
            })

            # Sites table: always the latest canonical record for this URL.
            upsert_site(self.url, self.job_id, s3_key, metadata)

        elif self.agent_type == 'ui-plan':
            output = UIPlanOutput.model_validate(raw_output)
            s3_key = save_plan(self.job_id, output.plan_markdown)
            # UI plan is saved to S3 only — not embedded or indexed in Pinecone.
            # plan_markdown and design_tokens are available via the artifact download endpoint.

        complete_artifact(self.job_id, _artifact_key(self.agent_type), s3_key)
        log_job_event(logger, f"{self.agent_type}_completed",
                      self.job_id, duration_ms=duration_ms, s3_key=s3_key)

    def on_error(self, error: Exception):
        artifact_key = _artifact_key(self.agent_type)
        fail_artifact(self.job_id, artifact_key, str(error))
        log_job_event(logger, f"{self.agent_type}_failed",
                      self.job_id, error=str(error))
```

### Artifact Key Mapping

```python
def _artifact_key(agent_type: str) -> str:
    return {
        'crawl':   'llmsTxt',
        'ui-plan': 'plan',
    }[agent_type]
```

### URL → Pinecone Vector ID

```python
import hashlib

def _url_vector_id(url: str) -> str:
    """
    Stable, fixed-length ID for a URL.
    Pinecone upserts by ID — using the URL hash means each re-crawl overwrites
    the previous vector for that site rather than accumulating duplicates.
    """
    return hashlib.md5(url.encode()).hexdigest()
```

| `agent_type` | Validates as | S3 save | Pinecone vector ID | Sites table | Pinecone metadata |
|-------------|-------------|---------|-------------------|-------------|-------------------|
| `crawl` | `CrawlOutput` | `save_llms_txt()` | `md5(url)` — overwrites previous vector | `upsert_site()` called | `SiteMetadata` fields |
| `ui-plan` | `UIPlanOutput` | `save_plan()` | — (not indexed) | — | — |

---

## Environment Variables

Both API keys are fetched from Secrets Manager via the extension — no application-level env vars needed for secrets. Lambda needs `AWS_SESSION_TOKEN` (provided automatically by the runtime) and `PINECONE_INDEX` (config, not a secret, set via Lambda env var in Phase 5).

IAM requires `secretsmanager:GetSecretValue` on both secret ARNs (outputs from `infra/modules/secrets/`). Both secrets are created in Phase 1 Terraform — see [01-terraform-storage.md](01-terraform-storage.md).

When Codex is added: same pattern — create `secrets/openai-api-key` in Secrets Manager and add `OPENAI_SECRET_NAME` to `src/constants.py`.

---

## Acceptance Criteria

- `create_agent("claude", ...)` returns a context with `submit_tool_name` stored
- `run_agent()` with a submit tool returns `block.input` dict when Claude calls it
- `on_complete` validates `block.input` as `CrawlOutput` or `UIPlanOutput` based on `agent_type`
- Only `crawl` embeds and upserts to Pinecone — `ui-plan` saves to S3 only
- `create_agent("codex", ...)` raises `NotImplementedError` with a helpful message
- `create_agent("unknown", ...)` raises `ValueError`
- Error hook calls `fail_artifact` with the error message
- `AgentHooks` base class exists so future providers implement the same interface
- Hooks are testable in isolation with mocked storage services

---

## Tests

**File:** `tests/test_llm.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_agent_returns_structured_output` | happy | `run_agent()` returns `block.input` dict when Claude calls the submit tool |
| `test_hooks_on_complete_crawl_embeds_upserts_and_updates_site` | happy | `crawl` calls `embed_text`, `upsert_vector` with URL as ID, and `upsert_site` |
| `test_hooks_on_complete_ui_plan_does_not_embed` | happy | `ui-plan` does not call `embed_text` or `upsert_vector` |
| `test_hooks_on_error_calls_fail_artifact` | unhappy | `on_error` calls `fail_artifact` with the error message string |
| `test_create_agent_unknown_raises_value_error` | unhappy | `create_agent("gpt-4", ...)` raises `ValueError` |
