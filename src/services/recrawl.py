import json
import os
import uuid

import boto3

from src.constants import AgentType, ArtifactType, JobType
from src.services.fargate import trigger_task
from src.services.logger import get_logger
from src.services.storage import create_job, fail_artifact, list_sites

logger = get_logger(__name__)

_sqs = boto3.client("sqs")


def handle_schedule(event: dict, context: object) -> dict:
    """EventBridge cron handler. Scans all crawled URLs and enqueues one SQS message per URL."""
    queue_url = os.environ["RECRAWL_QUEUE_URL"]
    sites = list_sites()
    for site in sites:
        _sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"url": site["url"], "model": site["model"]}),
        )
    logger.info({"event": "recrawl_scheduled", "count": len(sites)})
    return {"scheduled": len(sites)}


def handle_sqs(event: dict, context: object) -> dict:
    """SQS worker handler. Each record is one URL to re-crawl. Raises on failure so SQS retries the message."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        job_id = str(uuid.uuid4())
        create_job(job_id, body["url"], body["model"], JobType.CRAWL)
        try:
            trigger_task(AgentType.CRAWL, job_id, body["url"], body["model"])
            trigger_task(AgentType.UI_PLAN, job_id, body["url"], body["model"])
        except Exception as exc:
            logger.error({"event": "recrawl_dispatch_failed", "error": str(exc)})
            fail_artifact(job_id, ArtifactType.LLMS_TXT, str(exc))
            fail_artifact(job_id, ArtifactType.PLAN, str(exc))
            raise
    return {"processed": len(event["Records"])}
