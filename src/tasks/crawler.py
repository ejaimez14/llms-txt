import os

from src.constants import (
    CLAUDE_CRAWL_MODEL,
    CRAWLER_MAX_TURNS,
    CRAWLER_OUTPUT_FILE,
    CRAWLER_TIMEOUT_SECONDS,
    AgentType,
)
from src.models import CrawlOutput
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.tasks.base import TaskConfig, run_task

_CONFIG = TaskConfig(
    agent_type=AgentType.CRAWL,
    claude_model=CLAUDE_CRAWL_MODEL,
    max_turns=CRAWLER_MAX_TURNS,
    timeout_seconds=CRAWLER_TIMEOUT_SECONDS,
    output_file=CRAWLER_OUTPUT_FILE,
    output_model=CrawlOutput,
    system_prompt=CRAWL_SYSTEM_PROMPT,
    output_schema_hint="`llms_txt` (string) and `metadata` (object)",
    task_instruction="Crawl this website and produce an llms.txt file: {url}",
)

if __name__ == "__main__":
    run_task(
        job_id=os.environ["CRAWLER_JOB_ID"],
        url=os.environ["CRAWLER_URL"],
        model=os.environ["CRAWLER_MODEL"],
        config=_CONFIG,
    )
