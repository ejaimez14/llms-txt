import os
import sys

from src.constants import AgentType, ArtifactType
from src.services.logger import get_logger
from src.services.storage import fail_artifact

logger = get_logger(__name__)

_AGENT_ARTIFACT: dict[AgentType, ArtifactType] = {
    AgentType.CRAWL: ArtifactType.LLMS_TXT,
    AgentType.UI_PLAN: ArtifactType.PLAN,
    AgentType.REPORT: ArtifactType.REPORT,
    AgentType.COMPARE: ArtifactType.COMPARISON,
    AgentType.IMPLEMENT: ArtifactType.PR_URL,
}

_AGENT_TYPE_MAP: dict[str, AgentType] = {e.value: e for e in AgentType}


def main() -> None:
    # Deferred so a failed import can be reported to DynamoDB before exit.
    try:
        from src.tasks.base import run_task
        from src.tasks.registry import REGISTRY
    except Exception as exc:
        job_id = os.environ.get("AGENT_ID", "unknown")
        logger.error({"event": "startup_failed", "error": str(exc)})
        agent_type = _AGENT_TYPE_MAP.get(os.environ.get("AGENT_TYPE", ""))
        artifact_type = _AGENT_ARTIFACT.get(agent_type) if agent_type else None
        if artifact_type:
            fail_artifact(job_id, artifact_type, f"Startup error: {exc}")
        sys.exit(1)

    run_task(
        job_id=os.environ["AGENT_ID"],
        url=os.environ["AGENT_URL"],
        model=os.environ["AGENT_MODEL"],
        config=REGISTRY.get(AgentType(os.environ["AGENT_TYPE"])),
    )


main()
