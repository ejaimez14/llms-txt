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


def test_crawl_returns_202_with_job_id(mocker: MockerFixture) -> None:
    mocker.patch("src.handler.trigger_task")
    response = client.post("/api/crawl", json={"url": "https://example.com"})
    assert response.status_code == 202
    assert "jobId" in response.json()


def test_get_job_returns_artifact_statuses() -> None:
    storage.create_job("job-1", "https://example.com", "claude", JobType.CRAWL)
    response = client.get("/api/job", params={"id": "job-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["jobId"] == "job-1"
    assert body["status"] == JobStatus.PROCESSING
    assert ArtifactType.LLMS_TXT in body["artifacts"]
    assert ArtifactType.PLAN in body["artifacts"]
    assert (
        body["artifacts"][ArtifactType.LLMS_TXT]["status"] == ArtifactStatus.PROCESSING
    )


def test_get_artifact_returns_content() -> None:
    storage.create_job("job-1", "https://example.com", "claude", JobType.CRAWL)
    storage.save_llms_txt("job-1", "# Example llms.txt")
    storage.complete_artifact("job-1", ArtifactType.LLMS_TXT, "results/job-1/llms.txt")
    response = client.get("/api/job/job-1/llms-txt")
    assert response.status_code == 200
    assert response.json()["content"] == "# Example llms.txt"


def test_get_artifact_not_ready_returns_404() -> None:
    storage.create_job("job-1", "https://example.com", "claude", JobType.CRAWL)
    response = client.get("/api/job/job-1/plan")
    assert response.status_code == 404


def test_report_returns_404_if_not_crawled() -> None:
    response = client.post("/api/report", json={"url": "https://never-crawled.com"})
    assert response.status_code == 404
    assert "Crawl the site first" in response.json()["detail"]


def test_report_starts_reporter_and_returns_202(mocker: MockerFixture) -> None:
    storage.upsert_site(
        "https://example.com",
        "job-1",
        "results/job-1/llms.txt",
        {"tech_stack": [], "integrations": [], "content_types": []},
    )
    mock_run_in_thread = mocker.patch("src.handler._run_in_thread")
    response = client.post("/api/report", json={"url": "https://example.com"})
    assert response.status_code == 202
    assert "jobId" in response.json()
    mock_run_in_thread.assert_called_once()


def test_compare_same_id_returns_400() -> None:
    response = client.post(
        "/api/compare", json={"job_id_a": "same", "job_id_b": "same"}
    )
    assert response.status_code == 400


def test_compare_missing_job_returns_404() -> None:
    response = client.post(
        "/api/compare", json={"job_id_a": "missing-a", "job_id_b": "missing-b"}
    )
    assert response.status_code == 404


def test_compare_incomplete_job_returns_400() -> None:
    storage.create_job("job-a", "https://a.com", "claude", JobType.CRAWL)
    storage.create_job("job-b", "https://b.com", "claude", JobType.CRAWL)
    response = client.post(
        "/api/compare", json={"job_id_a": "job-a", "job_id_b": "job-b"}
    )
    assert response.status_code == 400
    assert "not complete" in response.json()["detail"]


def test_compare_starts_comparer_and_returns_202(mocker: MockerFixture) -> None:
    storage.create_job("job-a", "https://a.com", "claude", JobType.CRAWL)
    storage.create_job("job-b", "https://b.com", "claude", JobType.CRAWL)
    storage.complete_artifact("job-a", ArtifactType.LLMS_TXT, "results/job-a/llms.txt")
    storage.complete_artifact("job-a", ArtifactType.PLAN, "results/job-a/plan.md")
    storage.complete_artifact("job-b", ArtifactType.LLMS_TXT, "results/job-b/llms.txt")
    storage.complete_artifact("job-b", ArtifactType.PLAN, "results/job-b/plan.md")
    mock_run_in_thread = mocker.patch("src.handler._run_in_thread")
    response = client.post(
        "/api/compare", json={"job_id_a": "job-a", "job_id_b": "job-b"}
    )
    assert response.status_code == 202
    assert "jobId" in response.json()
    mock_run_in_thread.assert_called_once()
