import os
import sys

from src.constants import AgentType, ArtifactType
from src.services.storage import fail_artifact

_AGENT_ARTIFACT: dict[str, ArtifactType] = {
    "crawl": ArtifactType.LLMS_TXT,
    "ui-plan": ArtifactType.PLAN,
    "report": ArtifactType.REPORT,
    "compare": ArtifactType.COMPARISON,
    "implement": ArtifactType.PR_URL,
}

try:
    from src.tasks.base import run_task
    from src.tasks.registry import REGISTRY
except Exception as exc:
    job_id = os.environ.get("AGENT_ID", "unknown")
    artifact_type = _AGENT_ARTIFACT.get(os.environ.get("AGENT_TYPE", ""))
    if artifact_type:
        fail_artifact(job_id, artifact_type, f"Startup error: {exc}")
    print(f"Fatal startup error: {exc}", file=sys.stderr)
    sys.exit(1)

run_task(
    job_id=os.environ["AGENT_ID"],
    url=os.environ["AGENT_URL"],
    model=os.environ["AGENT_MODEL"],
    config=REGISTRY.get(AgentType(os.environ["AGENT_TYPE"])),
)
