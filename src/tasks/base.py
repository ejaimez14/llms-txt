import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import (
    AgentType,
    ArtifactType,
    IMPLEMENTER_BASE_BRANCH,
    IMPLEMENTER_REPO,
)
from src.models import TaskConfig
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger
from src.services.storage import get_artifact_content

logger = get_logger(__name__)


def run_task(job_id: str, url: str, model: str, config: TaskConfig) -> None:
    """Fargate entry point.

    Implement tasks use the Claude Code SDK (file-editing tools).
    All other tasks (crawl, ui-plan, report, compare) use the API directly
    via instructor (Claude) or the Agents SDK (OpenAI), both of which
    enforce structured output natively without requiring file I/O.
    """
    if config.agent_type == AgentType.IMPLEMENT:
        _run_implement_sdk(job_id, url, config)
    else:
        agent = create_agent(
            model=model,
            agent_type=config.agent_type,
            job_id=job_id,
            url=url,
            system_prompt=config.system_prompt,
        )
        run_agent(agent, config.task_instruction.format(url=url))


# --- Internal ---


def _run_implement_sdk(job_id: str, url: str, config: TaskConfig) -> None:
    hooks = JobHooks(job_id, config.agent_type, url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url, config))
    except Exception as exc:
        logger.error({"event": "implement_task_failed", "error": str(exc)})
        hooks.on_error(exc)
        raise


async def _run_sdk(hooks: JobHooks, url: str, config: TaskConfig) -> None:
    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=config.claude_model,
            permission_mode="bypassPermissions",
            allowed_tools=config.allowed_tools,
            max_turns=config.max_turns,
        )
        async with asyncio.timeout(config.timeout_seconds):
            async for _ in query(prompt=_build_implement_prompt(url, config), options=options):
                pass
        output = config.output_model.model_validate_json(
            Path(workspace, config.output_file).read_text()
        )
        hooks.on_complete(output.model_dump())


def _build_implement_prompt(url: str, config: TaskConfig) -> str:
    """Builds the implementer prompt by fetching the UI plan from storage and injecting repo context."""
    plan_content = get_artifact_content(url, ArtifactType.PLAN)
    if plan_content is None:
        raise ValueError(f"UI plan artifact unavailable for job {url}")

    branch_name = f"ui-implement/{os.environ['AGENT_ID'][:8]}"

    return (
        f"{config.system_prompt}\n\n"
        f"Repository: {IMPLEMENTER_REPO}\n"
        f"Base branch: {IMPLEMENTER_BASE_BRANCH}\n"
        f"Implementation branch: {branch_name}\n\n"
        f"Implement this UI plan:\n\n{plan_content}\n\n"
        f"After opening the GitHub PR, write your output as a JSON object to "
        f"`{config.output_file}` in the working directory. "
        f"The JSON must have exactly one field: {config.output_schema_hint}."
    )
