from enum import Enum


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    PARTIAL = "partial"  # all agents done, at least one failed


class JobType(str, Enum):
    CRAWL = "crawl"
    REPORT = "report"
    COMPARE = "compare"
    IMPLEMENT = "implement"


class ArtifactStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ArtifactType(str, Enum):
    LLMS_TXT = "llmsTxt"
    PLAN = "plan"
    REPORT = "report"
    COMPARISON = "comparison"
    PR_URL = "prUrl"


class ModelName(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


class AgentType(str, Enum):
    CRAWL = "crawl"
    UI_PLAN = "ui-plan"
    REPORT = "report"
    COMPARE = "compare"
    IMPLEMENT = "implement"


# --- Runtime Constants ---

CLAUDE_CRAWL_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_UI_PLAN_MODEL = "claude-sonnet-4-6"
CLAUDE_REPORT_MODEL = "claude-sonnet-4-6"
CLAUDE_COMPARE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_OUTPUT_TOKENS = 8192

TITAN_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
TITAN_EMBED_DIMENSIONS = 512
TITAN_MAX_INPUT_CHARS = 25000

AWS_REGION = "us-east-1"
LAMBDA_EXTENSION_URL = "http://localhost:2773"
LAMBDA_EXTENSION_TIMEOUT_SECONDS = 2
LAMBDA_EXTENSION_TOKEN_HEADER = "X-Aws-Parameters-Secrets-Token"

ANTHROPIC_SECRET_NAME = "secrets/anthropic-api-key"
PINECONE_SECRET_NAME = "secrets/pinecone-api-key"
OPENAI_SECRET_NAME = "secrets/openai-api-key"

OPENAI_CRAWL_MODEL = "gpt-4o-mini"
OPENAI_UI_PLAN_MODEL = "gpt-4o"

IMPLEMENT_MODEL = "claude-sonnet-4-6"
IMPLEMENTER_REPO = "https://github.com/ejaimez14/llms-txt-erick-jaimez"
IMPLEMENTER_BASE_BRANCH = "main"

IMPLEMENT_MAX_TURNS = 80
IMPLEMENT_TIMEOUT_SECONDS = 3600
IMPLEMENT_OUTPUT_FILE = "implement-output.json"
IMPLEMENT_OUTPUT_SCHEMA_HINT = "`pr_url` (string), `debug` (string, optional)"

AGENT_DEFAULT_MAX_TURNS = 30
AGENT_DEFAULT_TIMEOUT_SECONDS = 300

CRAWLER_ALLOWED_TOOLS = ["WebFetch", "Write"]
UI_PLANNER_ALLOWED_TOOLS = ["WebFetch", "Write"]
IMPLEMENT_ALLOWED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob"]

CLAUDE_AGENT_MODELS = {
    AgentType.CRAWL: CLAUDE_CRAWL_MODEL,
    AgentType.UI_PLAN: CLAUDE_UI_PLAN_MODEL,
    AgentType.REPORT: CLAUDE_REPORT_MODEL,
    AgentType.COMPARE: CLAUDE_COMPARE_MODEL,
}

OPENAI_AGENT_MODELS = {
    AgentType.CRAWL: OPENAI_CRAWL_MODEL,
    AgentType.UI_PLAN: OPENAI_UI_PLAN_MODEL,
    AgentType.REPORT: OPENAI_CRAWL_MODEL,
    AgentType.COMPARE: OPENAI_CRAWL_MODEL,
}

# --- Fargate Task Constants ---

CRAWLER_MAX_TURNS = 30
CRAWLER_TIMEOUT_SECONDS = 1800
CRAWLER_OUTPUT_FILE = "crawl-output.json"
CRAWLER_OUTPUT_SCHEMA_HINT = "`llms_txt` (string) and `metadata` (object)"
CRAWLER_TASK_INSTRUCTION = "Crawl this website and produce an llms.txt file: {url}"

UI_PLANNER_MAX_TURNS = 20
UI_PLANNER_TIMEOUT_SECONDS = 900
UI_PLANNER_OUTPUT_FILE = "ui-plan-output.json"
UI_PLANNER_OUTPUT_SCHEMA_HINT = "`plan_markdown` (string) and `design_tokens` (object)"
UI_PLANNER_TASK_INSTRUCTION = (
    "Analyze this website and produce a UI implementation plan: {url}"
)

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

# File extensions published to the /experimental UI preview — web assets only, so the
# implemented repo's source and config files are never served from the frontend bucket.
WEB_PREVIEW_EXTENSIONS = frozenset(
    {
        ".html",
        ".css",
        ".js",
        ".mjs",
        ".json",
        ".map",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
    }
)
