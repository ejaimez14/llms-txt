from dataclasses import dataclass

from src.constants import (
    CLAUDE_CRAWL_MODEL,
    CLAUDE_UI_PLAN_MODEL,
    CRAWLER_MAX_TURNS,
    CRAWLER_OUTPUT_FILE,
    CRAWLER_OUTPUT_SCHEMA_HINT,
    CRAWLER_TASK_INSTRUCTION,
    CRAWLER_TIMEOUT_SECONDS,
    UI_PLANNER_MAX_TURNS,
    UI_PLANNER_OUTPUT_FILE,
    UI_PLANNER_OUTPUT_SCHEMA_HINT,
    UI_PLANNER_TASK_INSTRUCTION,
    UI_PLANNER_TIMEOUT_SECONDS,
    AgentType,
)
from src.models import CrawlOutput, TaskConfig, UIPlanOutput
from src.prompts import CRAWL_SYSTEM_PROMPT, UI_PLAN_SYSTEM_PROMPT


@dataclass(frozen=True)
class TaskRegistry:
    crawl: TaskConfig
    ui_plan: TaskConfig

    def get(self, agent_type: AgentType) -> TaskConfig:
        """Returns the TaskConfig for the given agent type. Raises NotImplementedError for unregistered types."""
        mapping: dict[AgentType, TaskConfig] = {
            AgentType.CRAWL: self.crawl,
            AgentType.UI_PLAN: self.ui_plan,
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
    ),
)
