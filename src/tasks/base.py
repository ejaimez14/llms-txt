import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query
from claude_agent_sdk.types import HookContext

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
        raise


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
        hook_matchers = (
            [HookMatcher(matcher="WebFetch", hooks=[_make_page_limit_hook(config.max_pages, config.output_file)])]
            if config.max_pages is not None
            else []
        )
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=config.claude_model,
            permission_mode="bypassPermissions",
            allowed_tools=config.allowed_tools,
            max_turns=config.max_turns,
            hooks={"PreToolUse": hook_matchers} if hook_matchers else None,
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

    budget_note = (
        f"You may fetch at most {config.max_pages} pages total — choose the most important ones. "
        if config.max_pages is not None
        else ""
    )
    return (
        f"{config.system_prompt}\n\n"
        f"You have a maximum of {config.max_turns} turns. "
        f"{budget_note}"
        f"Write your output JSON to `{config.output_file}` in the working directory "
        f"before you run out of turns or pages. "
        f"The JSON must have exactly these fields: {config.output_schema_hint}.\n\n"
        f"{config.task_instruction.format(url=url)}"
    )


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


def _make_page_limit_hook(max_pages: int, output_file: str) -> Any:
    """Returns a PreToolUse hook that denies WebFetch calls after max_pages fetches.

    This is a hard structural limit enforced by the SDK — the model cannot bypass it.
    Once the cap is hit, the denial message directs the agent to write its output.
    """
    pages_fetched = {"count": 0}

    async def _hook(event: Any, session_id: str | None, context: HookContext) -> dict:
        if getattr(event, "tool_name", None) != "WebFetch":
            return {}
        pages_fetched["count"] += 1
        if pages_fetched["count"] > max_pages:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Page limit of {max_pages} reached. "
                        f"Write your output to `{output_file}` immediately."
                    ),
                }
            }
        return {}

    return _hook
