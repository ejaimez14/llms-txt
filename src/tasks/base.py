import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import AgentType, ArtifactType, IMPLEMENTER_BASE_BRANCH, IMPLEMENTER_REPO
from src.models import TaskConfig
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger
from src.services.storage import get_artifact_content

logger = get_logger(__name__)


def run_task(job_id: str, url: str, model: str, config: TaskConfig) -> None:
    """Fargate entry point.

    Implement uses Claude Code CLI — it needs a real filesystem for git and code operations.
    All other agent types route through llm.py: instructor for claude, OpenAI Agents SDK for openai.
    """
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
    hooks = JobHooks(job_id, config.agent_type, url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url, config))
    except Exception as exc:
        logger.error({"event": "implement_task_failed", "error": str(exc)})
        hooks.on_error(exc)
        raise


async def _run_sdk(hooks: JobHooks, url: str, config: TaskConfig) -> None:
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
        hooks.on_complete(output.model_dump())


def _build_implement_prompt(url: str, config: TaskConfig) -> str:
    """Builds the implementer prompt with literal shell commands (no placeholders).

    Auth is handled by the gh credential helper configured in entrypoint.sh —
    GITHUB_TOKEN in the environment is picked up automatically by gh auth git-credential.
    No token is embedded in URLs to avoid leaking it via git config or agent logs.
    """
    plan_content = get_artifact_content(url, ArtifactType.PLAN)
    if plan_content is None:
        raise ValueError(f"UI plan artifact unavailable for job {url}")

    branch_name = f"ui-implement/{os.environ['AGENT_ID'][:8]}"
    clone_cmd = f"git clone {IMPLEMENTER_REPO}.git repo"
    branch_cmd = f"git checkout -b {branch_name}"
    push_cmd = f"git add -A && git commit -m 'Implement UI plan' && git push origin {branch_name}"
    pr_cmd = (
        f"gh pr create"
        f" --title 'UI Implementation'"
        f" --body 'Automated UI implementation from plan'"
        f" --base {IMPLEMENTER_BASE_BRANCH}"
        f" --head {branch_name}"
    )

    return (
        f"{config.system_prompt}\n\n"
        f"Execute these exact steps in order:\n\n"
        f"1. Clone:          {clone_cmd}\n"
        f"2. Create branch:  cd repo && {branch_cmd}\n"
        f"3. Implement:      write all UI files directly inside repo/ (see ## UI Plan below)\n"
        f"4. Commit & push:  {push_cmd}\n"
        f"5. Create PR:      {pr_cmd}\n"
        f"   Capture the URL printed on stdout (e.g. https://github.com/.../pull/N).\n"
        f"6. Write output:   write `{config.output_file}` in the working directory (not inside repo/).\n"
        f"   Schema: {config.output_schema_hint}\n"
        f"   Example: {{\"pr_url\": \"<exact URL from step 5>\", \"debug\": \"\"}}\n\n"
        f"If any step fails, write `{config.output_file}` immediately with:\n"
        f"   {{\"pr_url\": \"\", \"debug\": \"step N failed: <exact error message from the failed command>\"}}\n"
        f"and stop. Include the full error output in debug.\n\n"
        f"## UI Plan\n\n{plan_content}"
    )
