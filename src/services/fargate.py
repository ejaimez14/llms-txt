import os

import boto3

from src.constants import (
    CRAWLER_TASK_COMMAND,
    IMPLEMENTER_TASK_COMMAND,
    UI_PLANNER_TASK_COMMAND,
)
from src.services.logger import get_logger

logger = get_logger(__name__)

_ecs = boto3.client("ecs", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

_CONTAINER_NAME = "agent"


def trigger_implementer_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs the implementer with the given parameters."""
    _run_task(
        event_name="fargate_implementer_dispatch_failed",
        command=IMPLEMENTER_TASK_COMMAND,
        environment=[
            {"name": "IMPLEMENTER_JOB_ID", "value": job_id},
            {"name": "IMPLEMENTER_URL", "value": url},
            {"name": "IMPLEMENTER_MODEL", "value": model},
        ],
    )


def trigger_crawler_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs the crawler with the given parameters."""
    _run_task(
        event_name="fargate_crawler_dispatch_failed",
        command=CRAWLER_TASK_COMMAND,
        environment=[
            {"name": "CRAWLER_JOB_ID", "value": job_id},
            {"name": "CRAWLER_URL", "value": url},
            {"name": "CRAWLER_MODEL", "value": model},
        ],
    )


def trigger_ui_planner_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs the UI planner with the given parameters."""
    _run_task(
        event_name="fargate_ui_planner_dispatch_failed",
        command=UI_PLANNER_TASK_COMMAND,
        environment=[
            {"name": "UI_PLANNER_JOB_ID", "value": job_id},
            {"name": "UI_PLANNER_URL", "value": url},
            {"name": "UI_PLANNER_MODEL", "value": model},
        ],
    )


# --- Internal ---


def _run_task(event_name: str, command: list[str], environment: list[dict]) -> None:
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_TASK_DEFINITION"],
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": os.environ["ECS_SUBNET_IDS"].split(","),
                    "securityGroups": [os.environ["ECS_SECURITY_GROUP"]],
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [
                    {
                        "name": _CONTAINER_NAME,
                        "command": command,
                        "environment": environment,
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": event_name, "error": str(exc)})
        raise
