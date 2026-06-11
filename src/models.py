from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from .constants import AgentType, ArtifactStatus, ArtifactType, JobStatus, ModelName

# --- Request models ---


class CrawlRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE


class ReportRequest(BaseModel):
    url: str


class CompareRequest(BaseModel):
    url: str
    model: ModelName = ModelName.CLAUDE


class ImplementRequest(BaseModel):
    job_id: str


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
    """Structured site-level metadata the crawl agent extracts; string fields are required so nulls never reach storage."""

    summary: str
    sentiment: str
    site_category: str
    industry: str
    primary_topics: list[str] = []
    tech_stack: list[str] = []
    integrations: list[str] = []
    business_model: str
    target_audience: str
    content_tone: str
    has_public_api: bool = False
    languages: list[str] = []


class CrawlOutput(BaseModel):
    """Structured output returned by the crawl agent's submit tool."""

    llms_txt: str  # full llms.txt formatted document
    metadata: SiteMetadata  # stored as Pinecone metadata for filtered search


class DesignTokens(BaseModel):
    """Exact CSS values extracted by the UI planner — included in UIPlanOutput, S3 only."""

    primary_color: str | None = None
    secondary_color: str | None = None
    background_color: str | None = None
    heading_font: str | None = None
    body_font: str | None = None
    css_framework: str | None = None


class UIPlanOutput(BaseModel):
    """Structured output returned by the UI planner agent's submit tool."""

    plan_markdown: str  # full implementation plan document
    design_tokens: DesignTokens  # stored as Pinecone metadata for UI similarity search


class ReportOutput(BaseModel):
    """Structured output returned by the reporter agent's submit tool."""

    report_markdown: str


class CompareOutput(BaseModel):
    """Structured output returned by the comparer agent's submit tool."""

    comparison_markdown: str


class ImplementOutput(BaseModel):
    """Structured output returned by the UI implementer agent."""

    pr_url: str
    debug: str = ""
    preview_url: str = ""


# --- Task config ---


@dataclass
class TaskConfig:
    """Config shape for a single Fargate agent task."""

    agent_type: AgentType
    claude_model: str
    max_turns: int
    timeout_seconds: int
    output_file: str
    output_model: type[BaseModel]
    system_prompt: str
    output_schema_hint: str
    task_instruction: str
    allowed_tools: list[str]


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
