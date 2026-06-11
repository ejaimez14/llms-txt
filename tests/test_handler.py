import os
from collections.abc import Generator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from pytest_mock import MockerFixture

import src.services.storage as storage
from src.constants import ArtifactStatus, ArtifactType, JobStatus, JobType, ModelName
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


def test_report_fires_both_models_and_returns_202(mocker: MockerFixture) -> None:
    storage.upsert_site(
        "https://example.com",
        "job-1",
        "results/job-1/llms.txt",
        {"tech_stack": [], "integrations": [], "content_types": []},
        "claude",
    )
    mock_enqueue_report = mocker.patch("src.handler.enqueue_report")
    response = client.post("/api/report", json={"url": "https://example.com"})

    assert response.status_code == 202
    body = response.json()
    assert "jobIdClaude" in body
    assert "jobIdOpenai" in body
    assert mock_enqueue_report.call_count == 2

    assert storage.get_job(body["jobIdClaude"])["model"] == ModelName.CLAUDE.value
    assert storage.get_job(body["jobIdOpenai"])["model"] == ModelName.OPENAI.value


def test_compare_returns_404_when_url_not_crawled() -> None:
    response = client.post("/api/compare", json={"url": "https://never-crawled.com"})
    assert response.status_code == 404
    assert "Crawl the site first" in response.json()["detail"]


def test_compare_returns_404_when_claude_report_missing() -> None:
    _seed_site("https://example.com")
    _seed_complete_report("rep-openai", "https://example.com", "openai")
    response = client.post("/api/compare", json={"url": "https://example.com"})
    assert response.status_code == 404
    assert "claude" in response.json()["detail"]


def test_get_pr_url_returns_pr_url() -> None:
    storage.create_job("job-impl", "parent-job", "claude", JobType.IMPLEMENT)
    storage.store_implement_result("job-impl", "https://github.com/owner/repo/pull/1")
    response = client.get("/api/job/job-impl/pr-url")
    assert response.status_code == 200
    assert response.json()["prUrl"] == "https://github.com/owner/repo/pull/1"


def test_get_pr_url_returns_preview_url() -> None:
    storage.create_job("job-impl", "parent-job", "claude", JobType.IMPLEMENT)
    storage.store_implement_result(
        "job-impl",
        "https://github.com/owner/repo/pull/1",
        "https://test.cloudfront.net/experimental/job-impl/",
    )
    response = client.get("/api/job/job-impl/pr-url")
    assert response.status_code == 200
    assert response.json()["previewUrl"] == (
        "https://test.cloudfront.net/experimental/job-impl/"
    )


def test_get_pr_url_not_ready_returns_404() -> None:
    storage.create_job("job-impl", "parent-job", "claude", JobType.IMPLEMENT)
    response = client.get("/api/job/job-impl/pr-url")
    assert response.status_code == 404


def test_get_pr_url_unknown_job_returns_404() -> None:
    response = client.get("/api/job/unknown-job-id/pr-url")
    assert response.status_code == 404


def test_compare_returns_404_when_openai_report_missing() -> None:
    _seed_site("https://example.com")
    _seed_complete_report("rep-claude", "https://example.com", "claude")
    response = client.post("/api/compare", json={"url": "https://example.com"})
    assert response.status_code == 404
    assert "openai" in response.json()["detail"]


def test_compare_returns_202_when_both_reports_complete(mocker: MockerFixture) -> None:
    _seed_site("https://example.com")
    _seed_complete_report("rep-claude", "https://example.com", "claude")
    _seed_complete_report("rep-openai", "https://example.com", "openai")
    mock_enqueue_compare = mocker.patch("src.handler.enqueue_compare")
    response = client.post("/api/compare", json={"url": "https://example.com"})
    assert response.status_code == 202
    assert "jobId" in response.json()
    mock_enqueue_compare.assert_called_once()

    enqueue_args = mock_enqueue_compare.call_args.args
    assert enqueue_args[1] == "rep-claude"  # claude report enqueued as job_id_a
    assert enqueue_args[2] == "rep-openai"  # openai report enqueued as job_id_b
    assert enqueue_args[3] == ModelName.CLAUDE.value  # defaults to claude
    compare_job = storage.get_job(response.json()["jobId"])
    assert compare_job["type"] == JobType.COMPARE


def test_compare_uses_requested_model(mocker: MockerFixture) -> None:
    _seed_site("https://example.com")
    _seed_complete_report("rep-claude", "https://example.com", "claude")
    _seed_complete_report("rep-openai", "https://example.com", "openai")
    mock_enqueue_compare = mocker.patch("src.handler.enqueue_compare")
    response = client.post(
        "/api/compare", json={"url": "https://example.com", "model": "openai"}
    )
    assert response.status_code == 202
    assert mock_enqueue_compare.call_args.args[3] == ModelName.OPENAI.value
    compare_job = storage.get_job(response.json()["jobId"])
    assert compare_job["model"] == ModelName.OPENAI.value


def _seed_site(url: str) -> None:
    storage.upsert_site(
        url,
        "crawl-1",
        "results/crawl-1/llms.txt",
        {"tech_stack": [], "integrations": [], "content_types": []},
        "claude",
    )


def _seed_complete_report(job_id: str, url: str, model: str) -> None:
    storage.create_job(job_id, url, model, JobType.REPORT)
    storage.complete_artifact(
        job_id, ArtifactType.REPORT, f"results/{job_id}/report.md"
    )
