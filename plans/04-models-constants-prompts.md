# Component: Models, Constants, and Prompts

## How to Use This Plan

You are implementing **Component 4: Models, Constants, and Prompts**. Your job is to produce three files:

- `src/constants.py` — enums for all shared string values (statuses, types, model names)
- `src/models.py` — Pydantic models for all request/response shapes
- `src/prompts.py` — system prompts for each agent

Every other component imports from these files. **Never use raw strings** for statuses, agent types, artifact types, or model names anywhere else in the codebase — always use the enums defined here.

Dependencies: **None** — no other component required.

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — imports `CrawlRequest`, `ModelName`, `AgentType`, `ArtifactType`
- [03-storage-service.md](03-storage-service.md) — imports `JobStatus`, `ArtifactType`
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — imports `AgentType`, `ModelName`
- [08-crawl-agent.md](08-crawl-agent.md) — imports `CRAWL_SYSTEM_PROMPT`
- [10-ui-planner-agent.md](10-ui-planner-agent.md) — imports `UI_PLAN_SYSTEM_PROMPT`
- [13-search-endpoint.md](13-search-endpoint.md) — imports `SearchResult`, `SearchResponse`

---

## Owner

Backend subagent

## Output Files

```
src/
  constants.py
  models.py
  prompts.py
```

---

## Part A: Constants (`src/constants.py`)

Use `str` enums so values serialize cleanly to JSON and compare equal to their string literals.

```python
from enum import Enum

class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE   = "complete"
    PARTIAL    = "partial"    # all agents done, at least one failed

class ArtifactStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE   = "complete"
    FAILED     = "failed"

class ArtifactType(str, Enum):
    LLMS_TXT = "llmsTxt"
    PLAN     = "plan"

class AgentType(str, Enum):
    CRAWL   = "crawl"
    UI_PLAN = "ui-plan"

class ModelName(str, Enum):
    CLAUDE = "claude"
    # CODEX = "codex"  # TO ADD CODEX: uncomment, add openai SDK dep, implement in 07-agent-factory-hooks.md
```

Model IDs are not enums — they're plain constants in the same file. `ModelName` is the external provider selector; these are the internal implementation versions used by the factory:

```python
# Crawl uses Haiku: content organization doesn't need heavy reasoning, and
# re-crawling 100 sites daily makes token cost the dominant expense.
# UI plan uses Sonnet: analyzing CSS design systems and producing actionable
# implementation plans benefits from stronger reasoning.
CLAUDE_CRAWL_MODEL   = "claude-haiku-4-5-20251001"
CLAUDE_UI_PLAN_MODEL = "claude-sonnet-4-6-20250514"
```

Update these two lines when upgrading model versions — nothing else needs to change.

---

## Part B: Pydantic Models (`src/models.py`)

All request bodies, response shapes, and internal data structures live here. Import these in the handler, storage service, and search endpoint.

```python
from __future__ import annotations
from pydantic import BaseModel
from .constants import JobStatus, ArtifactStatus, ArtifactType, ModelName

# --- Request models ---

class CrawlRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE

# --- Job / artifact models ---

class ArtifactRecord(BaseModel):
    status: ArtifactStatus
    s3Key: str | None = None
    error: str | None = None

class JobRecord(BaseModel):
    jobId: str
    url: str
    model: ModelName
    createdAt: str
    status: JobStatus
    artifacts: dict[ArtifactType, ArtifactRecord]

class JobSummary(BaseModel):
    """Lightweight record for list_jobs — no artifact content."""
    jobId: str
    url: str
    model: ModelName
    createdAt: str
    status: JobStatus
    artifacts: dict[ArtifactType, ArtifactStatus]

# --- Artifact retrieval ---

class ArtifactContent(BaseModel):
    jobId: str
    artifactType: ArtifactType
    content: str

# --- Agent structured outputs ---

class SiteMetadata(BaseModel):
    """Structured metadata the crawl agent extracts alongside the llms.txt content."""
    tech_stack:     list[str]  = []
    audience:       str | None = None
    tone:           str | None = None
    business_model: str | None = None
    integrations:   list[str]  = []
    content_types:  list[str]  = []

class CrawlOutput(BaseModel):
    """Structured output returned by the crawl agent's submit tool."""
    llms_txt: str           # full llms.txt formatted document
    metadata: SiteMetadata  # stored as Pinecone metadata for filtered search

class DesignTokens(BaseModel):
    """Exact CSS values extracted by the UI planner — included in UIPlanOutput, S3 only."""
    primary_color:    str | None = None
    secondary_color:  str | None = None
    background_color: str | None = None
    heading_font:     str | None = None
    body_font:        str | None = None
    css_framework:    str | None = None

class UIPlanOutput(BaseModel):
    """Structured output returned by the UI planner agent's submit tool."""
    plan_markdown: str          # full implementation plan document
    design_tokens: DesignTokens # stored as Pinecone metadata for UI similarity search

# --- Search ---

class SearchResult(BaseModel):
    jobId: str
    score: float
    url: str
    s3Key: str
    model: ModelName
    downloadUrl: str | None = None

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    error: str | None = None
```

---

## Part C: System Prompts (`src/prompts.py`)

One constant per agent. Keep prompts in this file so they can be tuned in one place without touching agent logic.

```python
CRAWL_SYSTEM_PROMPT = """
You are a web crawler that produces llms.txt files.

Given a website URL and a list of discovered pages (with their HTML content), produce a single
llms.txt document following this exact format:

1. H1 — the site or project name
2. Blockquote — a concise summary of what the site does and who it is for
3. Optional body text — important context, caveats, or notes (tech stack, audience, etc.)
4. H2 sections — group related pages into logical categories
5. Each link: `- [Page Title](URL): Brief description of what this page contains`
6. A final `## Optional` section for less critical pages (legal, privacy, careers)

Rules:
- Only include real URLs you were given — do not invent links
- Write descriptions that are useful to an LLM reading the file later
- Be concise but complete
- Follow the format exactly — no extra headings, no deviations

When you have gathered enough information, call the `submit_crawl_results` tool with:
- `llms_txt`: the complete document in the format above
- `metadata`: structured site metadata you observed during crawling.
  Use null for any field you cannot determine — never guess.

Do not return a text response. Always submit via the tool.
""".strip()

UI_PLAN_SYSTEM_PROMPT = """
You are a UI engineer that produces implementation plans for recreating website designs.

Given a website's HTML structure and CSS stylesheets, produce a detailed markdown plan that
another developer or agent could follow to rebuild the UI from scratch.

Your plan must include:

## Design Tokens
- Primary color: #hex (exact value from CSS)
- Secondary color: #hex
- Background: #hex
- Heading font: font-name, weight
- Body font: font-name, base size

## Layout Overview
- Overall page structure (header, main, sidebar, footer, etc.)
- Responsive behavior if evident from CSS

## [Section name] (one section per major UI region)
- Layout pattern (e.g. 3-column card grid, full-width hero)
- Key components with their visual properties
- Exact colors, spacing, and typography from CSS

## Component Inventory
Checkbox list of all distinct UI components to build

## Suggested Build Order
Ordered steps from layout scaffolding to final details

## Estimated Complexity
Low / Medium / High with a one-line justification

Rules:
- Use exact values from CSS — never estimate colors or fonts visually
- If CSS is not available, note it explicitly and describe structure only
- Be specific enough that an engineer can implement without seeing the site

When you have finished analyzing the site, call the `submit_ui_plan` tool with:
- `plan_markdown`: the complete implementation plan in the format above
- `design_tokens`: exact CSS values extracted from the stylesheets.
  Use null for any token you cannot find — never guess.

Do not return a text response. Always submit via the tool.
""".strip()
```

---

## Acceptance Criteria

- All enums use `str` as base class so they serialize to their string value in JSON
- `CrawlRequest` model is the single definition — imported by the handler, not redefined
- `CrawlOutput` and `UIPlanOutput` schemas are generated via `.model_json_schema()` for use as tool input schemas in agent files
- `SiteMetadata` and `DesignTokens` fields all default to `None` / `[]` — agents must not guess missing values
- `JobRecord` and `JobSummary` use the enums, not raw strings
- No other file in `src/` uses raw string literals for statuses, agent types, or model names
- System prompts live only in `prompts.py` — imported by the handler, not duplicated in agent files

---

## Tests

**File:** `tests/test_models.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_job_status_serializes_to_string` | happy | `JobStatus.COMPLETE` serializes to `"complete"` — confirms str enum pattern |
| `test_crawl_request_defaults_to_claude` | happy | `CrawlRequest(url="...")` has `model == ModelName.CLAUDE` |
| `test_crawl_request_rejects_unknown_model` | unhappy | `CrawlRequest(url="...", model="gpt-4")` raises `ValidationError` |
