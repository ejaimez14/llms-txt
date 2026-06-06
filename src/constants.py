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


# --- Runtime Constants ---

CLAUDE_CRAWL_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_UI_PLAN_MODEL = "claude-sonnet-4-6-20250514"

TITAN_EMBED_MODEL = "amazon.titan-embed-text-v1"
TITAN_MAX_INPUT_CHARS = 25000
