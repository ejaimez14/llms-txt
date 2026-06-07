# Component: UI Planner Agent

## How to Use This Plan

You are implementing **Component 10: UI Planner Agent**. Your job is to produce `src/agents/ui_planner.py`. The agent fetches a site's HTML and CSS, then generates a detailed UI implementation plan via a submit tool.

This agent is one of two started in parallel by a single `POST /crawl` request. Both share the same `job_id`. Do not implement S3 uploads or DynamoDB writes — hooks handle all persistence automatically.

Dependencies:
- [04-models-constants-prompts.md](04-models-constants-prompts.md) — `UI_PLAN_SYSTEM_PROMPT` from `src/prompts.py`, `UIPlanOutput` from `src/models.py`
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — `create_agent` and `run_agent` must be available

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — handler starts both crawl agents in parallel
- [08-crawl-agent.md](08-crawl-agent.md) — the other agent sharing the same `job_id`

---

## Owner

Agent subagent

## Output Files

```
src/
  agents/
    ui_planner.py
tests/
  test_ui_planner.py
```

---

## Entry Point

```python
def run_ui_planner(job_id: str, url: str, model: str) -> dict:
    """
    Creates agent via factory, runs it, returns the submit tool output.
    Hooks fire automatically — do not call storage functions here.
    """
```

---

## Behavior

1. Build the `UI_PLAN_TOOLS` list (`web_fetch` built-in + `submit_ui_plan` custom tool).
2. Call `create_agent` with `tools=UI_PLAN_TOOLS` and `submit_tool_name="submit_ui_plan"`.
3. Call `run_agent` with a user message containing the target URL.
4. The agent uses `web_fetch` to retrieve the page HTML and linked CSS stylesheets, then calls `submit_ui_plan` with the completed plan and design tokens.
5. The `on_complete` hook fires automatically — saves `plan.md` to S3, marks artifact complete.
6. Return the dict output from `run_agent`.

The agent drives the analysis itself — how many stylesheets it fetches and in what order is at the model's discretion.

---

## Tools

```python
from src.models import UIPlanOutput

SUBMIT_TOOL = {
    "name": "submit_ui_plan",
    "description": (
        "Call this when you have finished analyzing the site and are ready to submit. "
        "Provide the complete implementation plan and structured design tokens."
    ),
    "input_schema": UIPlanOutput.model_json_schema(),
}

UI_PLAN_TOOLS = [
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]
```

`web_fetch` is a built-in server-side tool — no implementation needed. `submit_ui_plan` is a custom tool; when the agent calls it, `run_agent` returns its input as a dict.

> **Note:** Verify the exact `type` string for `web_fetch` against the Anthropic tool use docs before implementing — use the latest available version identifier.

---

## Output Format — UI Plan

The submit tool's `plan_markdown` field must follow this structure:

```markdown
## Design Tokens
- Primary color: #hex  ← exact value from CSS
- Secondary color: #hex
- Background: #hex
- Heading font: font-name, weight
- Body font: font-name, base size

## Layout Overview
- Overall page structure
- Responsive behavior if evident

## [Section name]  ← one per major UI region
- Layout pattern
- Key components with visual properties
- Exact colors, spacing, typography from CSS

## Component Inventory
- [ ] Component name

## Suggested Build Order
1. Layout scaffolding
2. Design tokens
3. ...

## Estimated Complexity
Low / Medium / High — one-line justification
```

Colors and fonts must use exact values extracted from CSS — not visual estimates.

---

## Implementation

```python
from src.models import UIPlanOutput
from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

SUBMIT_TOOL = {
    "name": "submit_ui_plan",
    "description": (
        "Call this when you have finished analyzing the site and are ready to submit. "
        "Provide the complete implementation plan and structured design tokens."
    ),
    "input_schema": UIPlanOutput.model_json_schema(),
}

UI_PLAN_TOOLS = [
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]


def run_ui_planner(job_id: str, url: str, model: str) -> dict:
    """
    Creates agent via factory, runs it, returns the submit tool output.
    Hooks fire automatically — do not call storage functions here.
    """
    agent = create_agent(
        model=model,
        agent_type="ui-plan",
        job_id=job_id,
        url=url,
        system_prompt=UI_PLAN_SYSTEM_PROMPT,
        tools=UI_PLAN_TOOLS,
        submit_tool_name="submit_ui_plan",
    )
    return run_agent(agent, f"Analyze this website and produce a UI implementation plan: {url}")
```

---

## Acceptance Criteria

- Color and font values in the plan are exact (extracted from CSS), not approximated
- Plan is actionable enough for a developer to implement without seeing the site
- `run_ui_planner` never imports or calls `storage`, `embed_text`, or `upsert_vector`
- Works with both `claude` and `codex` model values via the agent factory

---

## Tests

**File:** `tests/test_ui_planner.py`
Use `pytest`. Mock `create_agent` and `run_agent` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_ui_planner_passes_correct_params` | happy | `create_agent` called with `agent_type="ui-plan"` and `submit_tool_name="submit_ui_plan"` |
| `test_run_ui_planner_returns_run_agent_output` | happy | return value of `run_agent` is passed through unchanged |
| `test_ui_planner_no_direct_storage_calls` | happy | `ui_planner.py` never imports `storage`, `embed_text`, or `upsert_vector` |
