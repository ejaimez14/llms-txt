import os
from collections.abc import Generator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from pytest_mock import MockerFixture

import src.services.storage as storage
from src.constants import ArtifactStatus, ArtifactType, JobStatus, JobType
from src.handler import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def aws_env() -> Generator[None, None, None]:
    """Activates moto, creates required AWS infrastructure, and reinitialises module-level clients."""
    with mock_aws():
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


def test_crawl_starts_both_agents(mocker: MockerFixture) -> None:
    """POST /api/crawl returns 202 with a jobId and kicks off background agents."""
    mock_thread = mocker.patch("src.handler._run_crawl_agents")
    mocker.patch("src.handler._run_in_thread", side_effect=lambda fn, *args: fn(*args))

    response = client.post("/api/crawl", json={"url": "https://example.com"})

    assert response.status_code == 202
    body = response.json()
    assert "jobId" in body
    assert body["status"] == "processing"
    mock_thread.assert_called_once()
    call_args = mock_thread.call_args[0]
    assert call_args[1] == "https://example.com"


def test_get_job_returns_artifact_statuses(mocker: MockerFixture) -> None:
    """GET /api/job?id=... returns the full job record with per-artifact statuses."""
    storage.create_job("job-status-1", "https://example.com", "claude", JobType.CRAWL)

    response = client.get("/api/job", params={"id": "job-status-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == "job-status-1"
    assert body["status"] == JobStatus.PROCESSING
    assert ArtifactType.LLMS_TXT in body["artifacts"]
    assert ArtifactType.PLAN in body["artifacts"]
    assert (
        body["artifacts"][ArtifactType.LLMS_TXT]["status"] == ArtifactStatus.PROCESSING
    )


def test_get_artifact_returns_content(mocker: MockerFixture) -> None:
    """GET /api/job/{id}/llms-txt returns content when the artifact is complete."""
    storage.create_job("job-content-1", "https://example.com", "claude", JobType.CRAWL)
    storage.save_llms_txt("job-content-1", "# Example llms.txt")
    storage.complete_artifact(
        "job-content-1", ArtifactType.LLMS_TXT, "results/job-content-1/llms.txt"
    )

    response = client.get("/api/job/job-content-1/llms-txt")

    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == "job-content-1"
    assert body["content"] == "# Example llms.txt"


def test_get_artifact_not_ready_returns_404(mocker: MockerFixture) -> None:
    """GET /api/job/{id}/plan returns 404 when the artifact is still processing."""
    storage.create_job(
        "job-not-ready-1", "https://example.com", "claude", JobType.CRAWL
    )

    response = client.get("/api/job/job-not-ready-1/plan")

    assert response.status_code == 404


def test_missing_url_returns_422() -> None:
    """POST /api/crawl without a url field returns 422 Unprocessable Entity."""
    response = client.post("/api/crawl", json={})

    assert response.status_code == 422


def test_report_returns_404_if_not_crawled() -> None:
    """POST /api/report returns 404 when no site record exists for the URL."""
    response = client.post("/api/report", json={"url": "https://never-crawled.com"})

    assert response.status_code == 404
    assert "Crawl the site first" in response.json()["detail"]


def test_report_starts_reporter_and_returns_202(mocker: MockerFixture) -> None:
    """POST /api/report returns 202 and starts the reporter when a site record exists."""
    storage.upsert_site(
        "https://example.com",
        "job-crawl-1",
        "results/job-crawl-1/llms.txt",
        {"tech_stack": [], "integrations": [], "content_types": []},
    )
    mock_reporter = mocker.patch("src.handler.run_reporter")
    mocker.patch("src.handler._run_in_thread", side_effect=lambda fn, *args: fn(*args))

    response = client.post("/api/report", json={"url": "https://example.com"})

    assert response.status_code == 202
    body = response.json()
    assert "jobId" in body
    assert body["status"] == "processing"
    mock_reporter.assert_called_once()


def test_compare_same_id_returns_400() -> None:
    """POST /api/compare with identical job IDs returns 400."""
    response = client.post(
        "/api/compare",
        json={"job_id_a": "same-id", "job_id_b": "same-id"},
    )

    assert response.status_code == 400
    assert "different" in response.json()["detail"]


def test_compare_missing_job_returns_404() -> None:
    """POST /api/compare returns 404 when one of the referenced jobs does not exist."""
    response = client.post(
        "/api/compare",
        json={"job_id_a": "does-not-exist", "job_id_b": "also-does-not-exist"},
    )

    assert response.status_code == 404


def test_compare_incomplete_job_returns_400() -> None:
    """POST /api/compare returns 400 when one of the referenced jobs is still processing."""
    storage.create_job("job-a-incomplete", "https://a.com", "claude", JobType.CRAWL)
    storage.create_job("job-b-incomplete", "https://b.com", "claude", JobType.CRAWL)

    response = client.post(
        "/api/compare",
        json={"job_id_a": "job-a-incomplete", "job_id_b": "job-b-incomplete"},
    )

    assert response.status_code == 400
    assert "not complete" in response.json()["detail"]


def test_compare_starts_comparer_and_returns_202(mocker: MockerFixture) -> None:
    """POST /api/compare returns 202 and starts the comparer when both jobs are complete."""
    storage.create_job("job-cmp-a", "https://a.com", "claude", JobType.CRAWL)
    storage.create_job("job-cmp-b", "https://b.com", "claude", JobType.CRAWL)
    # Complete both jobs
    storage.complete_artifact(
        "job-cmp-a", ArtifactType.LLMS_TXT, "results/job-cmp-a/llms.txt"
    )
    storage.complete_artifact(
        "job-cmp-a", ArtifactType.PLAN, "results/job-cmp-a/plan.md"
    )
    storage.complete_artifact(
        "job-cmp-b", ArtifactType.LLMS_TXT, "results/job-cmp-b/llms.txt"
    )
    storage.complete_artifact(
        "job-cmp-b", ArtifactType.PLAN, "results/job-cmp-b/plan.md"
    )

    mock_comparer = mocker.patch("src.handler.run_comparer")
    mocker.patch("src.handler._run_in_thread", side_effect=lambda fn, *args: fn(*args))

    response = client.post(
        "/api/compare",
        json={"job_id_a": "job-cmp-a", "job_id_b": "job-cmp-b"},
    )

    assert response.status_code == 202
    body = response.json()
    assert "jobId" in body
    assert body["status"] == "processing"
    mock_comparer.assert_called_once()
    call_args = mock_comparer.call_args[0]
    assert call_args[1] == "job-cmp-a"
    assert call_args[2] == "job-cmp-b"
