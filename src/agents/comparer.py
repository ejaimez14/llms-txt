from src.constants import AgentType, ArtifactType
from src.models import CompareOutput
from src.prompts import COMPARE_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent
from src.services.storage import fail_artifact, get_artifact_content, get_job

SUBMIT_TOOL = {
    "name": "submit_comparison",
    "description": (
        "Call this when you have finished your comparison and are ready to submit. "
        "Provide the complete comparison as markdown."
    ),
    "input_schema": CompareOutput.model_json_schema(),
}

COMPARE_TOOLS = [SUBMIT_TOOL]


def run_comparer(job_id: str, job_id_a: str, job_id_b: str, model: str) -> None:
    """Fetches llms.txt for both jobs and runs the comparison agent."""
    job_a = get_job(job_id_a)
    job_b = get_job(job_id_b)

    content_a = get_artifact_content(job_id_a, ArtifactType.LLMS_TXT)
    content_b = get_artifact_content(job_id_b, ArtifactType.LLMS_TXT)

    if not content_a or not content_b:
        fail_artifact(
            job_id,
            ArtifactType.COMPARISON,
            "llms.txt content unavailable for one or both jobs",
        )
        return

    user_message = _build_compare_message(job_a, content_a, job_b, content_b)
    agent = create_agent(
        model=model,
        agent_type=AgentType.COMPARE,
        job_id=job_id,
        url=job_a["url"],
        system_prompt=COMPARE_SYSTEM_PROMPT,
        tools=COMPARE_TOOLS,
        submit_tool_name="submit_comparison",
    )
    run_agent(agent, user_message)


# --- Internal ---


def _build_compare_message(
    job_a: dict, content_a: str, job_b: dict, content_b: str
) -> str:
    """Formats both llms.txt outputs into a labeled comparison message for the agent."""
    model_a = job_a.get("model", "unknown")
    model_b = job_b.get("model", "unknown")
    url_a = job_a.get("url", "")
    url_b = job_b.get("url", "")

    url_note = ""
    if url_a != url_b:
        url_note = f"\nNote: Job A is for {url_a} and Job B is for {url_b} — these are different URLs.\n"

    return (
        f"Compare these two llms.txt outputs for the same website.{url_note}\n\n"
        f"--- Model A ({model_a}) ---\n{content_a}\n\n"
        f"--- Model B ({model_b}) ---\n{content_b}"
    )
