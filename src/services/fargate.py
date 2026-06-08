import os

import boto3

from src.services.logger import get_logger

logger = get_logger(__name__)

_ecs = boto3.client("ecs", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


def trigger_implementer_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs run_implementer_task with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_IMPLEMENTER_TASK_DEFINITION"],
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
                        "name": "implementer",
                        "environment": [
                            {"name": "IMPLEMENTER_JOB_ID", "value": job_id},
                            {"name": "IMPLEMENTER_URL", "value": url},
                            {"name": "IMPLEMENTER_MODEL", "value": model},
                        ],
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_implementer_dispatch_failed", "error": str(exc)})
        raise


def trigger_crawler_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs run_crawler_task with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_CRAWLER_TASK_DEFINITION"],
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
                        "name": "crawler",
                        "environment": [
                            {"name": "CRAWLER_JOB_ID", "value": job_id},
                            {"name": "CRAWLER_URL", "value": url},
                            {"name": "CRAWLER_MODEL", "value": model},
                        ],
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_crawler_dispatch_failed", "error": str(exc)})
        raise


def trigger_ui_planner_task(job_id: str, url: str, model: str) -> None:
    """Dispatches a Fargate task that runs run_ui_planner_task with the given parameters."""
    try:
        _ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["ECS_UI_PLANNER_TASK_DEFINITION"],
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
                        "name": "ui-planner",
                        "environment": [
                            {"name": "UI_PLANNER_JOB_ID", "value": job_id},
                            {"name": "UI_PLANNER_URL", "value": url},
                            {"name": "UI_PLANNER_MODEL", "value": model},
                        ],
                    }
                ]
            },
        )
    except Exception as exc:
        logger.error({"event": "fargate_ui_planner_dispatch_failed", "error": str(exc)})
        raise
