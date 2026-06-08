import asyncio
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import ArtifactType, IMPLEMENT_MODEL
from src.prompts import IMPLEMENT_SYSTEM_PROMPT
from src.services.logger import get_logger
from src.services.storage import complete_artifact, fail_artifact, get_artifact_content

logger = get_logger(__name__)


def run_implementer(
    job_id: str,
    source_job_id: str,
    repo: str,
    base_branch: str,
) -> None:
    """
    Fetches the UI plan from source_job_id, runs the Claude Code agent to generate
    frontend files and open a GitHub PR, then marks the artifact complete.
    Called as the Fargate task entrypoint — must not raise.
    """
    plan_content = get_artifact_content(source_job_id, ArtifactType.PLAN)
    if not plan_content:
        fail_artifact(job_id, ArtifactType.PR_URL, "UI plan content unavailable")
        return

    try:
        asyncio.run(_run_agent(job_id, plan_content, repo, base_branch))
    except Exception as exc:
        logger.error({"event": "implementer_failed", "error": str(exc)})
        fail_artifact(job_id, ArtifactType.PR_URL, str(exc))


# --- Internal ---


async def _run_agent(
    job_id: str,
    plan_content: str,
    repo: str,
    base_branch: str,
) -> None:
    """Runs the claude-agent-sdk loop, reads the PR URL from pr-url.txt, and completes the artifact."""
    branch_name = f"ui-implement/{job_id[:8]}"

    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=IMPLEMENT_MODEL,
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob"],
            max_turns=80,
        )
        async with asyncio.timeout(3600):
            async for _ in query(
                prompt=_build_prompt(plan_content, repo, branch_name, base_branch),
                options=options,
            ):
                pass

        pr_url_path = Path(workspace, "pr-url.txt")
        if not pr_url_path.exists():
            raise FileNotFoundError("Agent did not produce pr-url.txt")

        pr_url = pr_url_path.read_text().strip()
        if not pr_url.startswith("https://github.com"):
            raise ValueError(f"Unexpected pr-url.txt content: {pr_url!r}")

        complete_artifact(job_id, ArtifactType.PR_URL, pr_url)


def _build_prompt(
    plan_content: str, repo: str, branch_name: str, base_branch: str
) -> str:
    """Builds the user-facing prompt with task-specific context."""
    return (
        f"{IMPLEMENT_SYSTEM_PROMPT}\n\n"
        f"Repository: {repo}\n"
        f"Base branch: {base_branch}\n"
        f"Implementation branch: {branch_name}\n\n"
        f"Implement this UI plan:\n\n{plan_content}"
    )
