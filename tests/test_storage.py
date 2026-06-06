import os
from collections.abc import Generator

import boto3
import pytest
from moto import mock_aws

from src.constants import ArtifactStatus, ArtifactType, JobStatus

# Environment variables must be set before importing storage so boto3 clients
# are created with moto-intercepted credentials.
os.environ.setdefault("BUCKET", "test-bucket")
os.environ.setdefault("TABLE", "test-jobs")
os.environ.setdefault("SITES_TABLE", "test-sites")

import src.services.storage as storage  # noqa: E402  (must follow env var setup)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def aws_env() -> Generator[None, None, None]:
    """
    Activates moto for all AWS services and creates the required infrastructure.
    Reinitialises the module-level boto3 clients so they use the moto session.
    autouse=True ensures every test runs with isolated, clean AWS state.
    """
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    with mock_aws():
        # Reinitialise module-level clients inside the moto context
        storage._s3 = boto3.client("s3", region_name="us-east-1")
        storage._dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        storage._s3.create_bucket(Bucket=os.environ["BUCKET"])

        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName=os.environ["TABLE"],
            KeySchema=[{"AttributeName": "jobId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "jobId", "AttributeType": "S"},
                {"AttributeName": "url", "AttributeType": "S"},
                {"AttributeName": "createdAt", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "url-createdAt-index",
                    "KeySchema": [
                        {"AttributeName": "url", "KeyType": "HASH"},
                        {"AttributeName": "createdAt", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        ddb.create_table(
            TableName=os.environ["SITES_TABLE"],
            KeySchema=[{"AttributeName": "url", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "url", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield


# ---------------------------------------------------------------------------
# DynamoDB tests
# ---------------------------------------------------------------------------


def test_create_job_initializes_all_artifacts() -> None:
    """Both artifact statuses must start as 'processing' after create_job."""
    storage.create_job("job-1", "https://example.com", "claude")

    job = storage.get_job("job-1")
    assert job is not None
    assert job["status"] == JobStatus.PROCESSING
    assert job["artifacts"][ArtifactType.LLMS_TXT]["status"] == ArtifactStatus.PROCESSING
    assert job["artifacts"][ArtifactType.PLAN]["status"] == ArtifactStatus.PROCESSING


def test_complete_artifact_sets_job_complete() -> None:
    """Overall status becomes 'complete' only when all artifacts succeed."""
    storage.create_job("job-2", "https://example.com", "claude")

    storage.complete_artifact("job-2", ArtifactType.LLMS_TXT, "results/job-2/llms.txt")
    job_after_first = storage.get_job("job-2")
    # One artifact still processing — overall must remain 'processing'
    assert job_after_first["status"] == JobStatus.PROCESSING

    storage.complete_artifact("job-2", ArtifactType.PLAN, "results/job-2/plan.md")
    job_after_second = storage.get_job("job-2")
    assert job_after_second["status"] == JobStatus.COMPLETE


def test_one_failed_sets_job_partial() -> None:
    """Overall status becomes 'partial' when all artifacts are done but one failed."""
    storage.create_job("job-3", "https://example.com", "claude")

    storage.complete_artifact("job-3", ArtifactType.LLMS_TXT, "results/job-3/llms.txt")
    storage.fail_artifact("job-3", ArtifactType.PLAN, "timeout")

    job = storage.get_job("job-3")
    assert job["status"] == JobStatus.PARTIAL
    assert job["artifacts"][ArtifactType.PLAN]["status"] == ArtifactStatus.FAILED
    assert job["artifacts"][ArtifactType.PLAN]["error"] == "timeout"


def test_get_artifact_content_not_complete_returns_none() -> None:
    """Returns None for an artifact whose status is still 'processing'."""
    storage.create_job("job-4", "https://example.com", "claude")

    result = storage.get_artifact_content("job-4", ArtifactType.LLMS_TXT)
    assert result is None


def test_list_jobs_for_url_returns_sorted_history() -> None:
    """list_jobs_for_url returns runs for a URL newest-first via GSI."""
    url = "https://example.com"
    storage.create_job("job-old", url, "claude")
    storage.create_job("job-new", url, "claude")

    jobs = storage.list_jobs_for_url(url)
    job_ids = [j["jobId"] for j in jobs]

    assert len(jobs) == 2
    assert set(job_ids) == {"job-old", "job-new"}
    # Newest createdAt comes first
    assert jobs[0]["createdAt"] >= jobs[1]["createdAt"]


def test_upsert_site_overwrites_previous() -> None:
    """Second upsert for same URL replaces the first — one row per URL always."""
    url = "https://example.com"
    metadata_v1 = {
        "tech_stack": ["React"],
        "audience": "developers",
        "tone": None,
        "business_model": None,
        "integrations": [],
        "content_types": [],
    }
    metadata_v2 = {
        "tech_stack": ["Vue"],
        "audience": "designers",
        "tone": "friendly",
        "business_model": "saas",
        "integrations": ["Stripe"],
        "content_types": ["blog"],
    }

    storage.upsert_site(url, "job-a", "results/job-a/llms.txt", metadata_v1)
    storage.upsert_site(url, "job-b", "results/job-b/llms.txt", metadata_v2)

    sites = storage.list_sites()
    url_records = [s for s in sites if s["url"] == url]

    assert len(url_records) == 1
    record = url_records[0]
    assert record["latestJobId"] == "job-b"
    assert record["tech_stack"] == ["Vue"]
    assert record["audience"] == "designers"


# ---------------------------------------------------------------------------
# S3 tests
# ---------------------------------------------------------------------------


def test_save_llms_txt_returns_correct_key() -> None:
    """save_llms_txt stores content and returns the expected S3 key."""
    key = storage.save_llms_txt("job-5", "# llms.txt content")
    assert key == "results/job-5/llms.txt"


def test_save_plan_returns_correct_key() -> None:
    """save_plan stores content and returns the expected S3 key."""
    key = storage.save_plan("job-6", "# plan content")
    assert key == "results/job-6/plan.md"


def test_get_artifact_content_returns_content_when_complete() -> None:
    """Returns S3 content when the artifact status is 'complete'."""
    storage.create_job("job-7", "https://example.com", "claude")
    storage.save_llms_txt("job-7", "hello llms.txt")
    storage.complete_artifact("job-7", ArtifactType.LLMS_TXT, "results/job-7/llms.txt")

    content = storage.get_artifact_content("job-7", ArtifactType.LLMS_TXT)
    assert content == "hello llms.txt"


def test_list_jobs_excludes_artifact_content() -> None:
    """list_jobs returns artifact statuses only — no s3Key or error fields."""
    storage.create_job("job-8", "https://example.com", "claude")
    storage.save_llms_txt("job-8", "content")
    storage.complete_artifact("job-8", ArtifactType.LLMS_TXT, "results/job-8/llms.txt")

    jobs = storage.list_jobs()
    assert len(jobs) == 1
    artifact = jobs[0]["artifacts"][ArtifactType.LLMS_TXT]
    assert "s3Key" not in artifact
    assert "error" not in artifact
    assert artifact["status"] == ArtifactStatus.COMPLETE
