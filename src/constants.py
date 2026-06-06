from enum import Enum


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    PARTIAL = "partial"  # all agents done, at least one failed


class ArtifactStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ArtifactType(str, Enum):
    LLMS_TXT = "llmsTxt"
    PLAN = "plan"


class AgentType(str, Enum):
    CRAWL = "crawl"
    UI_PLAN = "ui-plan"


class ModelName(str, Enum):
    CLAUDE = "claude"
    # CODEX = "codex"  # TO ADD CODEX: uncomment, add openai SDK dep, implement in 07-agent-factory-hooks.md


# Crawl uses Haiku: content organization doesn't need heavy reasoning, and
# re-crawling 100 sites daily makes token cost the dominant expense.
# UI plan uses Sonnet: analyzing CSS design systems and producing actionable
# implementation plans benefits from stronger reasoning.
CLAUDE_CRAWL_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_UI_PLAN_MODEL = "claude-sonnet-4-6-20250514"
