import os

import boto3

from src.constants import AgentType
from src.services.logger import get_logger

logger = get_logger(__name__)

_ecs = boto3.client(
    "ecs", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)

_TASK_COMMAND = ["python", "-m", "src.tasks"]
_IMPLEMENTER_COMMAND = ["python", "-m", "src.tasks.implementer"]
_CONTAINER_NAME = "agent"


def trigger_task(agent_type: AgentType, job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task for the given agent type."""
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
                        "environment": [
                            {"name": "AGENT_TYPE", "value": agent_type.value},
                            {"name": "AGENT_ID", "value": job_id},
                            {"name": "AGENT_URL", "value": url},
                            {"name": "AGENT_MODEL", "value": model},
                        ],
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


def trigger_implementer_task(
    job_id: str,
    source_job_id: str,
    repo: str,
    base_branch: str,
) -> None:
    """Dispatches a Fargate task that runs the UI implementer agent."""
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
                        "command": _IMPLEMENTER_COMMAND,
                        "environment": [
                            {"name": "IMPLEMENTER_JOB_ID", "value": job_id},
                            {
                                "name": "IMPLEMENTER_SOURCE_JOB_ID",
                                "value": source_job_id,
                            },
                            {"name": "IMPLEMENTER_REPO", "value": repo},
                            {"name": "IMPLEMENTER_BASE_BRANCH", "value": base_branch},
                        ],
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": "implementer_dispatch_failed", "error": str(exc)})
        raise
