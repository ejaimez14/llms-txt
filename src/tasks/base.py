import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import AgentType, ArtifactType
from src.models import TaskConfig
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger
from src.services.storage import get_artifact_content

logger = get_logger(__name__)


def run_task(job_id: str, url: str, model: str, config: TaskConfig) -> None:
    """Fargate entry point: routes to SDK loop (Claude) or agent factory (OpenAI)."""
    if model == "claude":
        _run_claude(job_id, url, config)
    else:
        _run_openai(job_id, url, model, config)


# --- Internal ---


def _run_claude(job_id: str, url: str, config: TaskConfig) -> None:
    hooks = JobHooks(job_id, config.agent_type, url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url, config))
    except Exception as exc:
        logger.error(
            {"event": f"{config.agent_type.value}_task_failed", "error": str(exc)}
        )
        hooks.on_error(exc)


def _run_openai(job_id: str, url: str, model: str, config: TaskConfig) -> None:
    agent = create_agent(
        model=model,
        agent_type=config.agent_type,
        job_id=job_id,
        url=url,
        system_prompt=config.system_prompt,
    )
    run_agent(agent, config.task_instruction.format(url=url))


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
            async for _ in query(prompt=_build_prompt(url, config), options=options):
                pass
        output = config.output_model.model_validate_json(
            Path(workspace, config.output_file).read_text()
        )
        hooks.on_complete(output.model_dump())


def _build_prompt(url: str, config: TaskConfig) -> str:
    if config.agent_type == AgentType.IMPLEMENT:
        return _build_implement_prompt(url, config)
    return (
        f"{config.system_prompt}\n\n"
        f"After completing your analysis, write your output as a JSON object to "
        f"`{config.output_file}` in the working directory. "
        f"The JSON must have exactly one field: {config.output_schema_hint}.\n\n"
        f"{config.task_instruction.format(url=url)}"
    )


def _build_implement_prompt(url: str, config: TaskConfig) -> str:
    """Builds the implementer prompt by fetching the UI plan from storage and injecting repo context."""
    plan_content = get_artifact_content(url, ArtifactType.PLAN)
    if plan_content is None:
        raise ValueError(f"UI plan artifact unavailable for job {url}")

    repo = os.environ["IMPLEMENTER_REPO"]
    base_branch = os.environ["IMPLEMENTER_BASE_BRANCH"]
    branch_name = f"ui-implement/{os.environ['AGENT_ID'][:8]}"

    return (
        f"{config.system_prompt}\n\n"
        f"Repository: {repo}\n"
        f"Base branch: {base_branch}\n"
        f"Implementation branch: {branch_name}\n\n"
        f"Implement this UI plan:\n\n{plan_content}\n\n"
        f"After opening the GitHub PR, write your output as a JSON object to "
        f"`{config.output_file}` in the working directory. "
        f"The JSON must have exactly one field: {config.output_schema_hint}."
    )
