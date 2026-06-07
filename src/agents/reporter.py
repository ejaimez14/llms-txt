from src.constants import AgentType, ArtifactType
from src.models import ReportOutput
from src.prompts import REPORT_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.storage import fail_artifact, get_artifact_content, get_site

SUBMIT_TOOL = {
    "name": "submit_report",
    "description": (
        "Call this when you have finished your analysis and are ready to submit. "
        "Provide the complete report as markdown."
    ),
    "input_schema": ReportOutput.model_json_schema(),
}

REPORT_TOOLS = [SUBMIT_TOOL]


def run_reporter(job_id: str, url: str, model: str) -> None:
    """Fetches the latest llms.txt for url and runs the report agent."""
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
        tools=REPORT_TOOLS,
        submit_tool_name="submit_report",
    )
    run_agent(agent, f"Generate a report for this site:\n\n{content}")
