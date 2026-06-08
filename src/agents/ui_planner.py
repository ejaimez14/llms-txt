from src.services.fargate import trigger_ui_planner_task


def run_ui_planner(job_id: str, url: str, model: str) -> None:
    """Dispatches the UI planning job to Fargate for both Claude and OpenAI."""
    trigger_ui_planner_task(job_id, url, model)
