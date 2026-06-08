import os

import boto3

from src.constants import AgentType
from src.services.logger import get_logger

logger = get_logger(__name__)

_ecs = boto3.client(
    "ecs", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)

_TASK_COMMAND = ["python", "-m", "src.tasks"]
_CONTAINER_NAME = "agent"


def trigger_task(
    agent_type: AgentType,
    job_id: str,
    url: str,
    model: str,
    extra_env: list[dict] | None = None,
) -> None:
    """Dispatches a Fargate task for the given agent type."""
    environment = [
        {"name": "AGENT_TYPE", "value": agent_type.value},
        {"name": "AGENT_ID", "value": job_id},
        {"name": "AGENT_URL", "value": url},
        {"name": "AGENT_MODEL", "value": model},
    ]
    if extra_env:
        environment.extend(extra_env)

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
                        "command": _TASK_COMMAND,
                        "environment": environment,
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error(
            {
                "event": "fargate_dispatch_failed",
                "error": str(exc),
                "agent_type": agent_type.value,
            }
        )
        raise
