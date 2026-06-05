# Component: UI Planner Agent

## How to Use This Plan

You are implementing **Component 10: UI Planner Agent**. Your job is to produce `src/agents/ui_planner.py`. The agent fetches a site's HTML and CSS, then generates a detailed implementation plan for recreating the UI.

This agent is one of **2 agents started in parallel** by a single `POST /crawl` request. Both share the same `job_id`. This agent's output is the `ArtifactType.PLAN` artifact. Do not implement S3 uploads or DynamoDB writes — SDK hooks handle all persistence.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — import `UI_PLAN_SYSTEM_PROMPT` from `src/prompts.py`. [07-agent-factory-hooks.md](07-agent-factory-hooks.md) must be available (or stubbed).

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — factory creates the agent; hooks call `complete_artifact(ArtifactType.PLAN, ...)`
- [02-lambda-handler.md](02-lambda-handler.md) — handler starts both agents in parallel

---

## Owner

Agent subagent

## Output Files

```
src/
  agents/
    ui_planner.py
```

---

## Entry Point

```python
from src.constants import ModelName
from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

def run_ui_planner(job_id: str, url: str, model: ModelName) -> str:
    """
    Creates agent via factory, runs it, returns the implementation plan.
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

## Agent Behavior

The model drives the analysis using tools — it is not a hardcoded pipeline. The agent:

1. Uses `web_fetch` to retrieve the target URL's HTML structure, class names, and inline styles
2. Uses `web_fetch` on linked CSS stylesheets to extract design tokens — colors, fonts, CSS variables, layout rules (up to 5, at the model's discretion)
3. Uses the extracted data to produce the final implementation plan as its `end_turn` response
4. The `on_complete` hook fires automatically — saves `plan.md` to S3, marks artifact complete

The agent does **not** call `save_plan` or `complete_job`. Hooks handle that.

---

## Tools

Two tools in `ui_planner.py`: one built-in server-side tool and one custom submit tool for structured output.

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

- `web_fetch` — built-in, runs server-side; used to retrieve the page HTML and linked CSS stylesheets
- `submit_ui_plan` — custom; Claude calls this at the end, returning a `UIPlanOutput`-shaped dict guaranteed to match the Pydantic schema

> **Note:** Verify the exact `type` string against the [Anthropic tool use docs](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool) before implementing. Use the latest available version.

---

## CSS Pre-processing

No custom preprocessing is needed. The model reads the raw CSS returned by `web_fetch` and extracts design tokens (CSS custom properties, colors, fonts, layout rules) as part of its reasoning. The system prompt instructs it to use exact values — not visual estimates.

---

## Plan Output Format

The agent produces a markdown document:

```markdown
# UI Implementation Plan: {site name}

## Recommended Tech Stack
- Framework: ...
- Styling: ...
- ...

## Page Structure
Overview of the page layout and major sections.

### Header / Navigation
- Nav links, logo placement, sticky/fixed behavior

### Hero Section
- Layout, headline, subheading, CTA placement

### [Additional sections derived from HTML structure...]

### Footer
- Columns, links, copyright

## Color Palette
- Primary: #hex  ← exact values from CSS
- Secondary: #hex
- Background: #hex
- Text: #hex
- Accent: #hex

## Typography
- Heading font: font-name, sizes used  ← exact values from CSS
- Body font: font-name, base size

## Component Inventory
- [ ] Navbar with responsive hamburger menu
- [ ] Hero with CTA button
- [ ] Feature cards (grid of N)
- [ ] ...

## Suggested Build Order
1. Layout scaffolding + routing
2. Design tokens (colors, typography)
3. ...

## Estimated Complexity
Low / Medium / High — with brief justification
```

Colors and fonts must use exact values extracted from CSS — not visual estimates.

---

## Acceptance Criteria

- Fetches HTML and up to 5 linked CSS stylesheets before calling the LLM
- Color and font values in the plan are exact (extracted from CSS), not approximated
- Plan is actionable enough for another agent or developer to implement from it
- No Playwright or Chromium dependency
- Works with both `claude` and `codex` model values
- Persistence handled entirely by hooks

---

## Tests

**File:** `tests/test_ui_planner.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_run_ui_planner_passes_correct_params` | happy | calls `create_agent` with `agent_type="ui-plan"` and `submit_tool_name="submit_ui_plan"` |
| `test_run_ui_planner_returns_run_agent_output` | happy | return value of `run_agent` is passed through unchanged |
| `test_ui_planner_no_direct_storage_calls` | happy | `ui_planner.py` never imports `storage`, `embed_text`, or `upsert_vector` |
