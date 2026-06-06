from __future__ import annotations

from pydantic import BaseModel

from .constants import ArtifactStatus, ArtifactType, JobStatus, ModelName

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

    tech_stack: list[str] = []
    audience: str | None = None
    tone: str | None = None
    business_model: str | None = None
    integrations: list[str] = []
    content_types: list[str] = []


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
