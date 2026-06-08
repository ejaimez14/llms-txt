import os

from src.constants import (
    CLAUDE_UI_PLAN_MODEL,
    UI_PLANNER_MAX_TURNS,
    UI_PLANNER_OUTPUT_FILE,
    UI_PLANNER_TIMEOUT_SECONDS,
    AgentType,
)
from src.models import UIPlanOutput
from src.prompts import UI_PLAN_SYSTEM_PROMPT
from src.tasks.base import TaskConfig, run_task

_CONFIG = TaskConfig(
    agent_type=AgentType.UI_PLAN,
    claude_model=CLAUDE_UI_PLAN_MODEL,
    max_turns=UI_PLANNER_MAX_TURNS,
    timeout_seconds=UI_PLANNER_TIMEOUT_SECONDS,
    output_file=UI_PLANNER_OUTPUT_FILE,
    output_model=UIPlanOutput,
    system_prompt=UI_PLAN_SYSTEM_PROMPT,
    output_schema_hint="`plan_markdown` (string) and `design_tokens` (object)",
    task_instruction="Analyze this website and produce a UI implementation plan: {url}",
)

if __name__ == "__main__":
    run_task(
        job_id=os.environ["UI_PLANNER_JOB_ID"],
        url=os.environ["UI_PLANNER_URL"],
        model=os.environ["UI_PLANNER_MODEL"],
        config=_CONFIG,
    )
