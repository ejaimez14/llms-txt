from src.models import CrawlOutput
from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent

SUBMIT_TOOL = {
    "name": "submit_crawl_results",
    "description": (
        "Call this when you have finished crawling and are ready to submit. "
        "Provide the complete llms.txt content and structured site metadata."
    ),
    "input_schema": CrawlOutput.model_json_schema(),
}

CRAWL_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search"},
    {"type": "web_fetch_20250305", "name": "web_fetch"},
    SUBMIT_TOOL,
]


def run_crawler(job_id: str, url: str, model: str) -> dict:
    """Runs the crawl agent against url and returns structured llms.txt content and site metadata."""
    agent = create_agent(
        model=model,
        agent_type="crawl",
        job_id=job_id,
        url=url,
        system_prompt=CRAWL_SYSTEM_PROMPT,
        tools=CRAWL_TOOLS,
        submit_tool_name="submit_crawl_results",
    )
    return run_agent(agent, f"Crawl this website and produce an llms.txt file: {url}")
