import asyncio
import os
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from src.constants import CLAUDE_CRAWL_MODEL, AgentType
from src.models import CrawlOutput
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.hooks import JobHooks
from src.services.llm import create_agent, run_agent
from src.services.logger import get_logger

logger = get_logger(__name__)

CRAWL_MAX_TURNS = 30
CRAWL_TIMEOUT_SECONDS = 1800
OUTPUT_FILE = "crawl-output.json"


def run_crawler_task(job_id: str, url: str, model: str) -> None:
    """Fargate entry point: routes to SDK loop (Claude) or agent factory (OpenAI)."""
    if model == "claude":
        _run_claude(job_id, url)
    else:
        _run_openai(job_id, url, model)


def _run_claude(job_id: str, url: str) -> None:
    """SDK-based crawl loop with manual hooks lifecycle."""
    hooks = JobHooks(job_id, AgentType.CRAWL, url, "claude")
    hooks.on_start()
    try:
        asyncio.run(_run_sdk(hooks, url))
    except Exception as exc:
        logger.error({"event": "crawler_task_failed", "error": str(exc)})
        hooks.on_error(exc)


def _run_openai(job_id: str, url: str, model: str) -> None:
    """Agent factory crawl — hooks lifecycle managed internally by run_agent."""
    agent = create_agent(
        model=model,
        agent_type=AgentType.CRAWL,
        job_id=job_id,
        url=url,
        system_prompt=CRAWL_SYSTEM_PROMPT,
    )
    run_agent(agent, f"Crawl this website and produce an llms.txt file: {url}")


async def _run_sdk(hooks: JobHooks, url: str) -> None:
    """Runs the claude-agent-sdk loop, reads crawl-output.json, and completes the artifact."""
    with tempfile.TemporaryDirectory() as workspace:
        options = ClaudeAgentOptions(
            cwd=workspace,
            model=CLAUDE_CRAWL_MODEL,
            permission_mode="bypassPermissions",
            allowed_tools=["WebFetch", "Write"],
            max_turns=CRAWL_MAX_TURNS,
        )
        await asyncio.wait_for(
            _exhaust(query(prompt=_build_prompt(url), options=options)),
            timeout=CRAWL_TIMEOUT_SECONDS,
        )
        output = CrawlOutput.model_validate_json(
            Path(workspace, OUTPUT_FILE).read_text()
        )
        hooks.on_complete(output.model_dump())


async def _exhaust(gen) -> None:
    async for message in gen:
        logger.info({"event": "crawler_message", "type": type(message).__name__})


def _build_prompt(url: str) -> str:
    """Combines system instructions with the file-writing requirement and target URL."""
    return (
        f"{CRAWL_SYSTEM_PROMPT}\n\n"
        f"After completing your analysis, write your output as a JSON object to "
        f"`{OUTPUT_FILE}` in the working directory. "
        f"The JSON must have exactly two fields: `llms_txt` (string) and `metadata` (object).\n\n"
        f"Crawl this website: {url}"
    )


if __name__ == "__main__":
    run_crawler_task(
        job_id=os.environ["CRAWLER_JOB_ID"],
        url=os.environ["CRAWLER_URL"],
        model=os.environ["CRAWLER_MODEL"],
    )
