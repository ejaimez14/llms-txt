from dataclasses import dataclass

from src.constants import (
    CLAUDE_CRAWL_MODEL,
    CLAUDE_UI_PLAN_MODEL,
    CRAWLER_ALLOWED_TOOLS,
    CRAWLER_MAX_TURNS,
    CRAWLER_OUTPUT_FILE,
    CRAWLER_OUTPUT_SCHEMA_HINT,
    CRAWLER_TASK_INSTRUCTION,
    CRAWLER_TIMEOUT_SECONDS,
    IMPLEMENT_ALLOWED_TOOLS,
    IMPLEMENT_MAX_TURNS,
    IMPLEMENT_MODEL,
    IMPLEMENT_OUTPUT_FILE,
    IMPLEMENT_OUTPUT_SCHEMA_HINT,
    IMPLEMENT_TIMEOUT_SECONDS,
    UI_PLANNER_ALLOWED_TOOLS,
    UI_PLANNER_MAX_TURNS,
    UI_PLANNER_OUTPUT_FILE,
    UI_PLANNER_OUTPUT_SCHEMA_HINT,
    UI_PLANNER_TASK_INSTRUCTION,
    UI_PLANNER_TIMEOUT_SECONDS,
    AgentType,
)
from src.models import CrawlOutput, ImplementOutput, TaskConfig, UIPlanOutput
from src.prompts import (
    CRAWL_SYSTEM_PROMPT,
    IMPLEMENT_SYSTEM_PROMPT,
    UI_PLAN_SYSTEM_PROMPT,
)


@dataclass(frozen=True)
class TaskRegistry:
    crawl: TaskConfig
    ui_plan: TaskConfig
    implement: TaskConfig

    def get(self, agent_type: AgentType) -> TaskConfig:
        """Returns the TaskConfig for the given agent type. Raises NotImplementedError for unregistered types."""
        mapping: dict[AgentType, TaskConfig] = {
            AgentType.CRAWL: self.crawl,
            AgentType.UI_PLAN: self.ui_plan,
            AgentType.IMPLEMENT: self.implement,
        }
        if agent_type not in mapping:
            raise NotImplementedError(f"No task config registered for {agent_type}")
        return mapping[agent_type]


REGISTRY = TaskRegistry(
    crawl=TaskConfig(
        agent_type=AgentType.CRAWL,
        claude_model=CLAUDE_CRAWL_MODEL,
        max_turns=CRAWLER_MAX_TURNS,
        timeout_seconds=CRAWLER_TIMEOUT_SECONDS,
        output_file=CRAWLER_OUTPUT_FILE,
        output_model=CrawlOutput,
        system_prompt=CRAWL_SYSTEM_PROMPT,
        output_schema_hint=CRAWLER_OUTPUT_SCHEMA_HINT,
        task_instruction=CRAWLER_TASK_INSTRUCTION,
        allowed_tools=CRAWLER_ALLOWED_TOOLS,
    ),
    ui_plan=TaskConfig(
        agent_type=AgentType.UI_PLAN,
        claude_model=CLAUDE_UI_PLAN_MODEL,
        max_turns=UI_PLANNER_MAX_TURNS,
        timeout_seconds=UI_PLANNER_TIMEOUT_SECONDS,
        output_file=UI_PLANNER_OUTPUT_FILE,
        output_model=UIPlanOutput,
        system_prompt=UI_PLAN_SYSTEM_PROMPT,
        output_schema_hint=UI_PLANNER_OUTPUT_SCHEMA_HINT,
        task_instruction=UI_PLANNER_TASK_INSTRUCTION,
        allowed_tools=UI_PLANNER_ALLOWED_TOOLS,
    ),
    implement=TaskConfig(
        agent_type=AgentType.IMPLEMENT,
        claude_model=IMPLEMENT_MODEL,
        max_turns=IMPLEMENT_MAX_TURNS,
        timeout_seconds=IMPLEMENT_TIMEOUT_SECONDS,
        output_file=IMPLEMENT_OUTPUT_FILE,
        output_model=ImplementOutput,
        system_prompt=IMPLEMENT_SYSTEM_PROMPT,
        output_schema_hint=IMPLEMENT_OUTPUT_SCHEMA_HINT,
        task_instruction="Implement the UI plan from job {url}.",
        allowed_tools=IMPLEMENT_ALLOWED_TOOLS,
    ),
)
