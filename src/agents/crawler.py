from src.prompts import CRAWL_SYSTEM_PROMPT
from src.services.llm import create_agent, run_agent


def run_crawler(job_id: str, url: str, model: str) -> dict:
    """Runs the crawl agent against url and returns structured llms.txt content and site metadata."""
    agent = create_agent(
        model=model,
        agent_type="crawl",
        job_id=job_id,
        url=url,
        system_prompt=CRAWL_SYSTEM_PROMPT,
    )
    return run_agent(agent, f"Crawl this website and produce an llms.txt file: {url}")
