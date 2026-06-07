from src.models import UIPlanOutput
from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

SUBMIT_TOOL = {
    "name": "submit_ui_plan",
    "description": (
        "Call this when you have finished analyzing the site and are ready to submit. "
        "Provide the complete implementation plan and structured design tokens."
    ),
    "input_schema": UIPlanOutput.model_json_schema(),
}

UI_PLAN_TOOLS = [
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]


def run_ui_planner(job_id: str, url: str, model: str) -> dict:
    """Fetches url and returns a structured UI implementation plan with design tokens."""
    agent = create_agent(
        model=model,
        agent_type="ui-plan",
        job_id=job_id,
        url=url,
        system_prompt=UI_PLAN_SYSTEM_PROMPT,
        tools=UI_PLAN_TOOLS,
        submit_tool_name="submit_ui_plan",
    )
    return run_agent(
        agent, f"Analyze this website and produce a UI implementation plan: {url}"
    )
