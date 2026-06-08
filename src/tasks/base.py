import asyncio
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import AgentType
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = get_logger(__name__)


@dataclass
class TaskConfig:
    agent_type: AgentType
    claude_model: str
    max_turns: int
    timeout_seconds: int
    output_file: str
    output_model: type["BaseModel"]
    system_prompt: str
    output_schema_hint: str
    task_instruction: str


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
        logger.error({"event": f"{config.agent_type.value}_task_failed", "error": str(exc)})
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
            allowed_tools=["WebFetch", "Write"],
            max_turns=config.max_turns,
        )
        await asyncio.wait_for(
            _exhaust(query(prompt=_build_prompt(url, config), options=options)),
            timeout=config.timeout_seconds,
        )
        output = config.output_model.model_validate_json(
            Path(workspace, config.output_file).read_text()
        )
        hooks.on_complete(output.model_dump())


async def _exhaust(gen: AsyncIterator[Any]) -> None:
    async for _ in gen:
        pass


def _build_prompt(url: str, config: TaskConfig) -> str:
    return (
        f"{config.system_prompt}\n\n"
        f"After completing your analysis, write your output as a JSON object to "
        f"`{config.output_file}` in the working directory. "
        f"The JSON must have exactly two fields: {config.output_schema_hint}.\n\n"
        f"{config.task_instruction.format(url=url)}"
    )
