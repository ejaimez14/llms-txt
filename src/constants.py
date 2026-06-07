from enum import Enum


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    PARTIAL = "partial"  # all agents done, at least one failed


class JobType(str, Enum):
    CRAWL = "crawl"
    REPORT = "report"
    COMPARE = "compare"


class ArtifactStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ArtifactType(str, Enum):
    LLMS_TXT = "llmsTxt"
    PLAN = "plan"
    REPORT = "report"
    COMPARISON = "comparison"


class AgentType(str, Enum):
    CRAWL = "crawl"
    UI_PLAN = "ui-plan"
    REPORT = "report"
    COMPARE = "compare"


class ModelName(str, Enum):
    CLAUDE = "claude"


# --- Runtime Constants ---

CLAUDE_CRAWL_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_UI_PLAN_MODEL = "claude-sonnet-4-6-20250514"
CLAUDE_REPORT_MODEL = "claude-sonnet-4-6-20250514"
CLAUDE_COMPARE_MODEL = "claude-sonnet-4-6-20250514"
CLAUDE_MAX_OUTPUT_TOKENS = 8192

TITAN_EMBED_MODEL = "amazon.titan-embed-text-v1"
TITAN_MAX_INPUT_CHARS = 25000

ANTHROPIC_SECRET_NAME = "secrets/anthropic-api-key"
PINECONE_SECRET_NAME = "secrets/pinecone-api-key"
