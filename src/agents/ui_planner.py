from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent


def run_ui_planner(job_id: str, url: str, model: str) -> dict:
    """Fetches url and returns a structured UI implementation plan with design tokens."""
    agent = create_agent(
        model=model,
        agent_type="ui-plan",
        job_id=job_id,
        url=url,
        system_prompt=UI_PLAN_SYSTEM_PROMPT,
    )
    return run_agent(
        agent, f"Analyze this website and produce a UI implementation plan: {url}"
    )
