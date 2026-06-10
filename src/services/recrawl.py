import json
import os
import uuid

import boto3

from src.agents.comparer import run_comparer
from src.agents.reporter import run_reporter
from src.constants import AgentType, JobType
from src.services.fargate import trigger_task
from src.services.logger import get_logger
from src.services.storage import create_job, list_sites

logger = get_logger(__name__)

_sqs = boto3.client("sqs")


def enqueue_report(job_id: str, url: str, model: str) -> None:
    """Enqueues an async report job for the SQS consumer to run."""
    _send({"type": "report", "jobId": job_id, "url": url, "model": model})


def enqueue_compare(job_id: str, job_id_a: str, job_id_b: str, model: str) -> None:
    """Enqueues an async compare job for the SQS consumer to run."""
    _send(
        {
            "type": "compare",
            "jobId": job_id,
            "jobIdA": job_id_a,
            "jobIdB": job_id_b,
            "model": model,
        }
    )


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
    """SQS worker handler. Dispatches each record by "type" (report/compare) or falls back to re-crawl. Raises on failure so SQS retries the message."""
    for record in event["Records"]:
        body = json.loads(record["body"])
        message_type = body.get("type")
        if message_type == "report":
            run_reporter(body["jobId"], body["url"], body["model"])
        elif message_type == "compare":
            run_comparer(body["jobId"], body["jobIdA"], body["jobIdB"], body["model"])
        else:
            job_id = str(uuid.uuid4())
            create_job(job_id, body["url"], body["model"], JobType.CRAWL)
            trigger_task(AgentType.CRAWL, job_id, body["url"], body["model"])
            trigger_task(AgentType.UI_PLAN, job_id, body["url"], body["model"])
    return {"processed": len(event["Records"])}


# --- Internal ---


def _send(message: dict) -> None:
    """Sends a JSON message to the recrawl SQS queue."""
    _sqs.send_message(
        QueueUrl=os.environ["RECRAWL_QUEUE_URL"],
        MessageBody=json.dumps(message),
    )
