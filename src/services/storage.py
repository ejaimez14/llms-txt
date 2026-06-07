import os
from datetime import UTC, datetime
from typing import Any

import boto3
import boto3.dynamodb.conditions as dynamo_conditions
from botocore.exceptions import ClientError

from src.constants import ArtifactStatus, ArtifactType, JobStatus, JobType
from src.services.logger import get_logger

_s3 = boto3.client("s3")
_dynamodb = boto3.resource("dynamodb")

logger = get_logger(__name__)

_JOB_ARTIFACTS: dict[str, list[str]] = {
    JobType.CRAWL: [ArtifactType.LLMS_TXT, ArtifactType.PLAN],
    JobType.REPORT: [ArtifactType.REPORT],
    JobType.COMPARE: [ArtifactType.COMPARISON],
}


# --- S3 Operations ---


def save_llms_txt(job_id: str, content: str) -> str:
    """Saves llms.txt content to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/llms.txt"
    _put_s3_object(s3_key, content)
    return s3_key


def save_plan(job_id: str, content: str) -> str:
    """Saves plan markdown to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/plan.md"
    _put_s3_object(s3_key, content)
    return s3_key


def save_report(job_id: str, content: str) -> str:
    """Saves report markdown to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/report.md"
    _put_s3_object(s3_key, content)
    return s3_key


def save_comparison(job_id: str, content: str) -> str:
    """Saves comparison markdown to S3. Returns the S3 key."""
    s3_key = f"results/{job_id}/comparison.md"
    _put_s3_object(s3_key, content)
    return s3_key


def get_artifact_content(job_id: str, artifact_type: str) -> str | None:
    """
    Reads artifact content from S3 via its DynamoDB record.
    Returns None if the artifact is not complete or does not exist.
    """
    job = get_job(job_id)
    if job is None:
        return None

    artifact = job.get("artifacts", {}).get(artifact_type)
    if artifact is None or artifact.get("status") != ArtifactStatus.COMPLETE:
        return None

    s3_key = artifact.get("s3Key")
    if not s3_key:
        return None

    return _get_s3_object(s3_key)


def generate_download_url(s3_key: str, expiry: int = 3600) -> str:
    """Generates a presigned S3 URL for private downloads."""
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": s3_key},
        ExpiresIn=expiry,
    )


# --- DynamoDB Operations ---


def create_job(
    job_id: str, url: str, model: str, job_type: str = JobType.CRAWL
) -> None:
    """
    Writes the initial job record with overall status 'processing'.
    Initializes artifacts based on job_type — crawl gets llmsTxt + plan,
    report and compare each get a single artifact.
    """
    table = _jobs_table()
    processing_artifact = {"status": ArtifactStatus.PROCESSING}
    artifact_types = _JOB_ARTIFACTS.get(job_type, [])
    try:
        table.put_item(
            Item={
                "jobId": job_id,
                "url": url,
                "model": model,
                "type": job_type,
                "createdAt": _utc_now(),
                "status": JobStatus.PROCESSING,
                "artifacts": {t: processing_artifact for t in artifact_types},
            }
        )
    except ClientError as exc:
        logger.error({"event": "create_job_failed", "error": str(exc)})
        raise


def complete_artifact(
    job_id: str,
    artifact_type: str,
    s3_key: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """
    Marks one artifact as complete and stores its s3Key and token counts.
    Recalculates and updates the overall job status.
    """
    table = _jobs_table()
    try:
        response = table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET artifacts.#artifact = :artifact_val",
            ExpressionAttributeNames={"#artifact": artifact_type},
            ExpressionAttributeValues={
                ":artifact_val": {
                    "status": ArtifactStatus.COMPLETE,
                    "s3Key": s3_key,
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                },
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        logger.error({"event": "complete_artifact_failed", "error": str(exc)})
        raise
    _recalculate_job_status(response["Attributes"])


def fail_artifact(job_id: str, artifact_type: str, error: str) -> None:
    """
    Marks one artifact as failed and stores the error message.
    Recalculates and updates the overall job status.
    """
    table = _jobs_table()
    try:
        response = table.update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET artifacts.#artifact = :artifact_val",
            ExpressionAttributeNames={"#artifact": artifact_type},
            ExpressionAttributeValues={
                ":artifact_val": {"status": ArtifactStatus.FAILED, "error": error},
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        logger.error({"event": "fail_artifact_failed", "error": str(exc)})
        raise
    _recalculate_job_status(response["Attributes"])


def get_job(job_id: str) -> dict | None:
    """Reads full job record from DynamoDB. Returns None if not found."""
    table = _jobs_table()
    try:
        response = table.get_item(Key={"jobId": job_id})
    except ClientError as exc:
        logger.error({"event": "get_job_failed", "error": str(exc)})
        raise
    return response.get("Item")


def list_jobs(model_filter: str | None = None) -> list[dict]:
    """
    Scans DynamoDB for all jobs, returning lightweight records only.
    Excludes artifact s3Key and error fields. Sorted by createdAt descending.
    Optionally filters by model.
    """
    table = _jobs_table()
    # ProjectionExpression keeps artifact statuses but excludes content fields
    projection = "jobId, #url, model, createdAt, #status, artifacts"
    kwargs: dict = {
        "ProjectionExpression": projection,
        "ExpressionAttributeNames": {"#url": "url", "#status": "status"},
    }
    if model_filter is not None:
        kwargs["FilterExpression"] = dynamo_conditions.Attr("model").eq(model_filter)

    try:
        response = table.scan(**kwargs)
        jobs = response.get("Items", [])

        # DynamoDB scan may paginate — collect all pages
        while "LastEvaluatedKey" in response:
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.scan(**kwargs)
            jobs.extend(response.get("Items", []))
    except ClientError as exc:
        logger.error({"event": "list_jobs_failed", "error": str(exc)})
        raise

    jobs.sort(key=lambda j: j.get("createdAt", ""), reverse=True)
    return [_slim_job(job) for job in jobs]


def list_jobs_for_url(url: str) -> list[dict]:
    """
    Returns all crawl runs for a specific URL, newest-first.
    Queries the url-createdAt-index GSI — no table scan.
    """
    table = _jobs_table()
    try:
        response = table.query(
            IndexName="url-createdAt-index",
            KeyConditionExpression=dynamo_conditions.Key("url").eq(url),
            ScanIndexForward=False,
        )
    except ClientError as exc:
        logger.error({"event": "list_jobs_for_url_failed", "error": str(exc)})
        raise
    return response.get("Items", [])


# --- Sites Table Operations ---


def upsert_site(url: str, job_id: str, s3_key: str, metadata: dict) -> None:
    """
    Creates or overwrites the canonical site record for this URL.
    SiteMetadata fields are stored flat so they can be used directly as Pinecone metadata.
    """
    table = _sites_table()
    try:
        table.put_item(
            Item={
                "url": url,
                "latestJobId": job_id,
                "latestS3Key": s3_key,
                "lastCrawledAt": _utc_now(),
                # SiteMetadata fields stored flat (not nested)
                "tech_stack": metadata.get("tech_stack", []),
                "audience": metadata.get("audience"),
                "tone": metadata.get("tone"),
                "business_model": metadata.get("business_model"),
                "integrations": metadata.get("integrations", []),
                "content_types": metadata.get("content_types", []),
            }
        )
    except ClientError as exc:
        logger.error({"event": "upsert_site_failed", "error": str(exc)})
        raise


def get_site(url: str) -> dict | None:
    """Returns the latest site record for a URL, or None if never crawled."""
    table = _sites_table()
    try:
        response = table.get_item(Key={"url": url})
    except ClientError as exc:
        logger.error({"event": "get_site_failed", "error": str(exc)})
        raise
    return response.get("Item")


def list_sites() -> list[dict]:
    """
    Scans the sites table — one record per unique URL ever crawled.
    Used by the scheduler and the History tab.
    """
    table = _sites_table()
    try:
        response = table.scan()
        sites = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            sites.extend(response.get("Items", []))
    except ClientError as exc:
        logger.error({"event": "list_sites_failed", "error": str(exc)})
        raise

    return sites


# --- Internal ---


def _bucket() -> str:
    """Returns the S3 bucket name."""
    return os.environ["BUCKET"]


def _jobs_table() -> Any:
    """Returns the DynamoDB Table resource for the jobs table."""
    return _dynamodb.Table(os.environ["TABLE"])


def _sites_table() -> Any:
    """Returns the DynamoDB Table resource for the sites table."""
    return _dynamodb.Table(os.environ["SITES_TABLE"])


def _utc_now() -> str:
    """Returns the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _put_s3_object(s3_key: str, content: str) -> None:
    """Writes a string object to S3."""
    try:
        _s3.put_object(Bucket=_bucket(), Key=s3_key, Body=content.encode("utf-8"))
    except ClientError as exc:
        logger.error({"event": "put_s3_object_failed", "error": str(exc)})
        raise


def _get_s3_object(s3_key: str) -> str | None:
    """Reads an object from S3, returning None if it does not exist."""
    try:
        response = _s3.get_object(Bucket=_bucket(), Key=s3_key)
        return response["Body"].read().decode("utf-8")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchKey":
            return None
        logger.error({"event": "get_s3_object_failed", "error": str(exc)})
        raise


def _recalculate_job_status(job: dict) -> None:
    """
    Updates overall status and token totals based on the job's current artifact map.
    Accepts the full job record returned by update_item to avoid a redundant get_item call.
    """
    job_id = job["jobId"]
    artifacts = job.get("artifacts", {})
    artifact_records = list(artifacts.values())
    statuses = [artifact.get("status") for artifact in artifact_records]

    if any(s == ArtifactStatus.PROCESSING for s in statuses):
        return  # still in flight — no overall status change yet

    overall = (
        JobStatus.COMPLETE
        if all(s == ArtifactStatus.COMPLETE for s in statuses)
        else JobStatus.PARTIAL
    )

    total_input_tokens = sum(
        artifact.get("inputTokens", 0) for artifact in artifact_records
    )
    total_output_tokens = sum(
        artifact.get("outputTokens", 0) for artifact in artifact_records
    )

    try:
        _jobs_table().update_item(
            Key={"jobId": job_id},
            UpdateExpression="SET #status = :status, totalInputTokens = :input, totalOutputTokens = :output",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": overall,
                ":input": total_input_tokens,
                ":output": total_output_tokens,
            },
        )
    except ClientError as exc:
        logger.error({"event": "recalculate_job_status_failed", "error": str(exc)})
        raise


def _slim_job(job: dict) -> dict:
    """
    Strips artifact s3Key and error fields from a job record for lightweight list responses.
    """
    slim_artifacts = {
        artifact_type: {"status": artifact.get("status")}
        for artifact_type, artifact in job.get("artifacts", {}).items()
    }
    return {
        "jobId": job.get("jobId"),
        "url": job.get("url"),
        "model": job.get("model"),
        "createdAt": job.get("createdAt"),
        "status": job.get("status"),
        "artifacts": slim_artifacts,
    }
