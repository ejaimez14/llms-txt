from src.services.fargate import trigger_crawler_task


def run_crawler(job_id: str, url: str, model: str) -> None:
    """Dispatches the crawl job to Fargate for both Claude and OpenAI."""
    trigger_crawler_task(job_id, url, model)
