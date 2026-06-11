import asyncio
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import AgentType
from src.models import ImplementOutput, TaskConfig
from src.prompts import _build_implement_prompt
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger
from src.services.storage import publish_experimental_preview

logger = get_logger(__name__)


def run_task(job_id: str, url: str, model: str, config: TaskConfig) -> None:
    """Routes implement jobs to the Claude Code SDK; all other types through llm.py."""
    if config.agent_type == AgentType.IMPLEMENT:
        _run_implement(job_id, url, config)
    else:
        agent = create_agent(
            model,
            config.agent_type,
            job_id,
            url,
            config.system_prompt,
            max_turns=config.max_turns,
            timeout_seconds=config.timeout_seconds,
        )
        run_agent(agent, config.task_instruction.format(url=url))


# --- Internal ---


def _run_implement(job_id: str, url: str, config: TaskConfig) -> None:
    """Runs the implement task: sets up hooks, delegates to the Claude Code SDK, handles errors."""
    hooks = JobHooks(job_id, config.agent_type, url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url, config))
    except Exception as exc:
        logger.error({"event": "implement_task_failed", "error": str(exc)})
        hooks.on_error(exc)
        raise


async def _run_sdk(hooks: JobHooks, url: str, config: TaskConfig) -> None:
    """Drives the SDK query loop in a temp workspace and calls hooks.on_complete."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=config.claude_model,
            permission_mode="bypassPermissions",
            allowed_tools=config.allowed_tools,
            max_turns=config.max_turns,
        )
        output_path = Path(workspace, config.output_file)
        async with asyncio.timeout(config.timeout_seconds):
            async for _ in query(prompt=_build_implement_prompt(url, config), options=options):
                if output_path.exists():
                    break
        output = config.output_model.model_validate_json(
            Path(workspace, config.output_file).read_text()
        )
        _publish_implement_preview(config, output, workspace, hooks.job_id)
        hooks.on_complete(output.model_dump())


def _publish_implement_preview(
    config: TaskConfig, output: ImplementOutput, workspace: str, job_id: str
) -> None:
    """Publishes the implemented UI preview when an implement job successfully opened a PR."""
    if config.agent_type != AgentType.IMPLEMENT or not output.pr_url:
        return
    repo_dir = Path(workspace, "repo")
    if repo_dir.is_dir():
        output.preview_url = publish_experimental_preview(job_id, str(repo_dir))
