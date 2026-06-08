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


class ModelName(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


class AgentType(str, Enum):
    CRAWL = "crawl"
    UI_PLAN = "ui-plan"
    REPORT = "report"
    COMPARE = "compare"


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
OPENAI_SECRET_NAME = "secrets/openai-api-key"

OPENAI_CRAWL_MODEL = "gpt-4o-mini"
OPENAI_UI_PLAN_MODEL = "gpt-4o"

CLAUDE_AGENT_MODELS = {
    AgentType.CRAWL:   CLAUDE_CRAWL_MODEL,
    AgentType.UI_PLAN: CLAUDE_UI_PLAN_MODEL,
    AgentType.REPORT:  CLAUDE_REPORT_MODEL,
    AgentType.COMPARE: CLAUDE_COMPARE_MODEL,
}

OPENAI_AGENT_MODELS = {
    AgentType.CRAWL:   OPENAI_CRAWL_MODEL,
    AgentType.UI_PLAN: OPENAI_UI_PLAN_MODEL,
    AgentType.REPORT:  OPENAI_CRAWL_MODEL,
    AgentType.COMPARE: OPENAI_CRAWL_MODEL,
}

# --- Fargate Task Constants ---

IMPLEMENTER_TASK_COMMAND = ["python", "-m", "src.tasks.implementer"]
CRAWLER_TASK_COMMAND = ["python", "-m", "src.tasks.crawler"]
UI_PLANNER_TASK_COMMAND = ["python", "-m", "src.tasks.ui_planner"]

CRAWLER_MAX_TURNS = 30
CRAWLER_TIMEOUT_SECONDS = 1800
CRAWLER_OUTPUT_FILE = "crawl-output.json"

UI_PLANNER_MAX_TURNS = 20
UI_PLANNER_TIMEOUT_SECONDS = 900
UI_PLANNER_OUTPUT_FILE = "ui-plan-output.json"

# Anthropic server-side tools passed per agent type. Only crawl and ui-plan need web access.
CLAUDE_EXTRA_TOOLS: dict[AgentType, list[dict]] = {
    AgentType.CRAWL: [
        {"type": "web_search_20250305", "name": "web_search"},
        {"type": "web_fetch_20250305", "name": "web_fetch"},
    ],
    AgentType.UI_PLAN: [
        {"type": "web_fetch_20250305", "name": "web_fetch"},
    ],
}
