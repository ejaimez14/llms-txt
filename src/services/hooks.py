import hashlib
import time

from src.constants import AgentType, ArtifactType
from src.models import CompareOutput, CrawlOutput, ReportOutput, UIPlanOutput
from src.services.embeddings import embed_text
from src.services.logger import get_logger, log_job_event
from src.services.pinecone_client import upsert_vector
from src.services.storage import (
    complete_artifact,
    fail_artifact,
    save_comparison,
    save_llms_txt,
    save_plan,
    save_report,
    store_implement_result,
    upsert_site,
)

logger = get_logger(__name__)


class JobHooks:
    """Lifecycle hooks for all agent types (provider-agnostic).

    Handles all persistence (S3, DynamoDB, Pinecone) and structured logging
    so agents stay focused on their task.
    """

    def __init__(
        self, job_id: str, agent_type: AgentType, url: str, model: str
    ) -> None:
        self.job_id = job_id
        self.agent_type = agent_type
        self.url = url
        self.model = model
        self._start_time: float | None = None

    def on_start(self) -> None:
        self._start_time = time.time()
        log_job_event(
            logger,
            f"{self.agent_type}_started",
            self.job_id,
            url=self.url,
            model=self.model,
        )

    def on_complete(self, raw_output: dict | str, usage: object | None = None) -> None:
        """Persist agent output to S3, DynamoDB, and (for crawl) Pinecone."""
        duration_ms = int((time.time() - self._start_time) * 1000)

        if self.agent_type == AgentType.CRAWL:
            output = CrawlOutput.model_validate(raw_output)
            s3_key = save_llms_txt(self.job_id, output.llms_txt)
            metadata = output.metadata.model_dump()

            # Pinecone vector ID is a URL hash so re-crawling overwrites rather than accumulates.
            vector = embed_text(output.llms_txt)
            upsert_vector(
                _url_vector_id(self.url),
                vector,
                {
                    "url": self.url,
                    "s3Key": s3_key,
                    "model": self.model,
                    "artifact": "crawl",
                    **metadata,
                },
            )

            upsert_site(self.url, self.job_id, s3_key, metadata, self.model)

        elif self.agent_type == AgentType.UI_PLAN:
            output = UIPlanOutput.model_validate(raw_output)
            s3_key = save_plan(self.job_id, output.plan_markdown)
            # UI plan is saved to S3 only — not embedded or indexed in Pinecone.

        elif self.agent_type == AgentType.REPORT:
            output = ReportOutput.model_validate(raw_output)
            s3_key = save_report(self.job_id, output.report_markdown)

        elif self.agent_type == AgentType.COMPARE:
            output = CompareOutput.model_validate(raw_output)
            s3_key = save_comparison(self.job_id, output.comparison_markdown)

        elif self.agent_type == AgentType.IMPLEMENT:
            pr_url = raw_output["pr_url"]
            preview_url = raw_output.get("preview_url", "")
            store_implement_result(self.job_id, pr_url, preview_url)
            log_job_event(
                logger,
                f"{self.agent_type}_completed",
                self.job_id,
                duration_ms=duration_ms,
                pr_url=pr_url,
                preview_url=preview_url,
            )
            return

        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        complete_artifact(
            self.job_id,
            _artifact_key(self.agent_type),
            s3_key,
            input_tokens,
            output_tokens,
        )
        log_job_event(
            logger,
            f"{self.agent_type}_completed",
            self.job_id,
            duration_ms=duration_ms,
            s3_key=s3_key,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def on_error(self, error: Exception) -> None:
        artifact_key = _artifact_key(self.agent_type)
        fail_artifact(self.job_id, artifact_key, str(error))
        log_job_event(
            logger, f"{self.agent_type}_failed", self.job_id, error=str(error)
        )


# --- Internal ---


def _artifact_key(agent_type: AgentType) -> ArtifactType:
    return {
        AgentType.CRAWL: ArtifactType.LLMS_TXT,
        AgentType.UI_PLAN: ArtifactType.PLAN,
        AgentType.REPORT: ArtifactType.REPORT,
        AgentType.COMPARE: ArtifactType.COMPARISON,
        AgentType.IMPLEMENT: ArtifactType.PR_URL,
    }[agent_type]


def _url_vector_id(url: str) -> str:
    """Returns a stable MD5 hash of the URL so re-crawls overwrite rather than duplicate the Pinecone vector."""
    return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()
