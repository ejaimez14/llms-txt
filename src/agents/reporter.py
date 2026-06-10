from src.constants import AgentType, ArtifactType
from src.prompts import REPORT_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger
from src.services.storage import fail_artifact, get_artifact_content, get_site

logger = get_logger(__name__)


def run_reporter(job_id: str, url: str, model: str) -> None:
    """Fetches the latest llms.txt for url and runs the report agent."""
    try:
        site = get_site(url)
        if not site:
            fail_artifact(job_id, ArtifactType.REPORT, f"No crawl found for {url}")
            return
        content = get_artifact_content(site["latestJobId"], ArtifactType.LLMS_TXT)
        if not content:
            fail_artifact(job_id, ArtifactType.REPORT, "llms.txt content unavailable")
            return
        agent = create_agent(
            model=model,
            agent_type=AgentType.REPORT,
            job_id=job_id,
            url=url,
            system_prompt=REPORT_SYSTEM_PROMPT,
        )
        run_agent(agent, f"Generate a report for this site:\n\n{content}")
    except Exception as exc:
        logger.error({"event": "reporter_failed", "error": str(exc)})
        fail_artifact(job_id, ArtifactType.REPORT, str(exc))
        raise
