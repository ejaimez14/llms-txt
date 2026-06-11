import os
from collections.abc import Generator

import boto3
import pytest
from moto import mock_aws

import src.services.storage as storage
from src.constants import ArtifactStatus, ArtifactType, JobStatus, JobType, ModelName


@pytest.fixture(autouse=True)
def aws_env() -> Generator[None, None, None]:
    """Activates moto, creates required infrastructure, and reinitialises module-level clients."""
    with mock_aws():
        storage._s3 = boto3.client("s3", region_name="us-east-1")
        storage._dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        storage._s3.create_bucket(Bucket=os.environ["BUCKET"])
        storage._s3.create_bucket(Bucket=os.environ["FRONTEND_BUCKET"])

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


def test_create_job_initializes_all_artifacts() -> None:
    """Both artifact statuses must start as 'processing' after create_job."""
    storage.create_job("job-1", "https://example.com", "claude")

    job = storage.get_job("job-1")
    assert job["status"] == JobStatus.PROCESSING
    assert (
        job["artifacts"][ArtifactType.LLMS_TXT]["status"] == ArtifactStatus.PROCESSING
    )
    assert job["artifacts"][ArtifactType.PLAN]["status"] == ArtifactStatus.PROCESSING


def test_complete_artifact_sets_job_complete() -> None:
    """Overall status becomes 'complete' only when all artifacts succeed."""
    storage.create_job("job-2", "https://example.com", "claude")

    storage.complete_artifact("job-2", ArtifactType.LLMS_TXT, "results/job-2/llms.txt")
    assert storage.get_job("job-2")["status"] == JobStatus.PROCESSING

    storage.complete_artifact("job-2", ArtifactType.PLAN, "results/job-2/plan.md")
    assert storage.get_job("job-2")["status"] == JobStatus.COMPLETE


def test_one_failed_sets_job_partial() -> None:
    """Overall status becomes 'partial' when all artifacts are done but one failed."""
    storage.create_job("job-3", "https://example.com", "claude")
    storage.complete_artifact("job-3", ArtifactType.LLMS_TXT, "results/job-3/llms.txt")
    storage.fail_artifact("job-3", ArtifactType.PLAN, "timeout")

    job = storage.get_job("job-3")
    assert job["status"] == JobStatus.PARTIAL
    assert job["artifacts"][ArtifactType.PLAN]["status"] == ArtifactStatus.FAILED


def test_get_artifact_content_not_complete_returns_none() -> None:
    """Returns None for an artifact whose status is still 'processing'."""
    storage.create_job("job-4", "https://example.com", "claude")
    assert storage.get_artifact_content("job-4", ArtifactType.LLMS_TXT) is None


def test_get_artifact_content_returns_content_when_complete() -> None:
    """Returns S3 content when the artifact status is 'complete'."""
    storage.create_job("job-5", "https://example.com", "claude")
    storage.save_llms_txt("job-5", "hello llms.txt")
    storage.complete_artifact("job-5", ArtifactType.LLMS_TXT, "results/job-5/llms.txt")

    assert (
        storage.get_artifact_content("job-5", ArtifactType.LLMS_TXT) == "hello llms.txt"
    )


def test_save_llms_txt_returns_correct_key() -> None:
    assert storage.save_llms_txt("job-6", "content") == "results/job-6/llms.txt"


def test_save_plan_returns_correct_key() -> None:
    assert storage.save_plan("job-7", "content") == "results/job-7/plan.md"


def test_list_jobs_excludes_artifact_content() -> None:
    """list_jobs returns artifact statuses only — no s3Key or error fields."""
    storage.create_job("job-8", "https://example.com", "claude")
    storage.complete_artifact("job-8", ArtifactType.LLMS_TXT, "results/job-8/llms.txt")

    artifact = storage.list_jobs()[0]["artifacts"][ArtifactType.LLMS_TXT]
    assert "s3Key" not in artifact
    assert artifact["status"] == ArtifactStatus.COMPLETE


def test_list_jobs_for_url_returns_sorted_history() -> None:
    """list_jobs_for_url returns runs for a URL newest-first via GSI."""
    storage.create_job("job-old", "https://example.com", "claude")
    storage.create_job("job-new", "https://example.com", "claude")

    jobs = storage.list_jobs_for_url("https://example.com")
    assert len(jobs) == 2
    assert jobs[0]["createdAt"] >= jobs[1]["createdAt"]


def test_upsert_site_overwrites_previous() -> None:
    """Second upsert for same URL replaces the first — one row per URL always."""
    metadata = {
        "site_category": "docs",
        "primary_topics": ["payments"],
        "tech_stack": ["React"],
        "integrations": ["Stripe"],
        "business_model": "saas-subscription",
        "target_audience": "devs",
        "content_tone": "technical",
        "has_public_api": True,
        "languages": ["en"],
    }
    storage.upsert_site(
        "https://example.com", "job-a", "results/job-a/llms.txt", metadata, "claude"
    )

    metadata["tech_stack"] = ["Vue"]
    storage.upsert_site(
        "https://example.com", "job-b", "results/job-b/llms.txt", metadata, "claude"
    )

    sites = storage.list_sites()
    assert len(sites) == 1
    site = sites[0]
    assert site["latestJobId"] == "job-b"
    # Every redesigned field persists flat (renames included) so search filters stay intact.
    assert site["tech_stack"] == ["Vue"]
    assert site["site_category"] == "docs"
    assert site["primary_topics"] == ["payments"]
    assert site["integrations"] == ["Stripe"]
    assert site["business_model"] == "saas-subscription"
    assert site["target_audience"] == "devs"
    assert site["content_tone"] == "technical"
    assert site["has_public_api"] is True
    assert site["languages"] == ["en"]


def test_report_and_compare_jobs_initialize_correct_artifacts() -> None:
    """Report and compare jobs each get only their own artifact — not llmsTxt or plan."""
    storage.create_job("job-r", "https://example.com", "claude", JobType.REPORT)
    report_job = storage.get_job("job-r")
    assert report_job["type"] == JobType.REPORT
    assert ArtifactType.REPORT in report_job["artifacts"]
    assert ArtifactType.LLMS_TXT not in report_job["artifacts"]

    storage.create_job("job-c", "https://example.com", "claude", JobType.COMPARE)
    compare_job = storage.get_job("job-c")
    assert compare_job["type"] == JobType.COMPARE
    assert ArtifactType.COMPARISON in compare_job["artifacts"]
    assert ArtifactType.LLMS_TXT not in compare_job["artifacts"]


def test_report_job_resolves_complete_on_single_artifact() -> None:
    """Report job status becomes 'complete' when its single artifact completes."""
    storage.create_job("job-r2", "https://example.com", "claude", JobType.REPORT)
    storage.complete_artifact("job-r2", ArtifactType.REPORT, "results/job-r2/report.md")

    assert storage.get_job("job-r2")["status"] == JobStatus.COMPLETE


def test_save_report_and_comparison_return_correct_keys() -> None:
    assert storage.save_report("job-r3", "content") == "results/job-r3/report.md"
    assert (
        storage.save_comparison("job-c3", "content") == "results/job-c3/comparison.md"
    )


def test_store_implement_result_sets_pr_url_and_completes_job() -> None:
    storage.create_job("job-impl", "parent-job-id", "claude", JobType.IMPLEMENT)
    storage.store_implement_result(
        "job-impl",
        "https://github.com/owner/repo/pull/1",
        "https://test.cloudfront.net/experimental/job-impl/",
    )
    job = storage.get_job("job-impl")
    artifact = job["artifacts"][ArtifactType.PR_URL]
    assert job["status"] == JobStatus.COMPLETE
    assert artifact["status"] == ArtifactStatus.COMPLETE
    assert artifact["prUrl"] == "https://github.com/owner/repo/pull/1"
    assert artifact["previewUrl"] == "https://test.cloudfront.net/experimental/job-impl/"
    assert "s3Key" not in artifact


def test_publish_experimental_preview_uploads_web_assets_only(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.css").write_text("body{}")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret")
    # Source/config files must NOT be served from the public preview path.
    (tmp_path / "main.py").write_text("print('x')")
    (tmp_path / "README.md").write_text("# repo")

    preview_url = storage.publish_experimental_preview("job-impl", str(tmp_path))

    assert preview_url == "https://test.cloudfront.net/experimental/job-impl/"
    bucket = os.environ["FRONTEND_BUCKET"]
    keys = {
        obj["Key"]
        for obj in storage._s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    }
    assert keys == {
        "experimental/job-impl/index.html",
        "experimental/job-impl/assets/app.css",
    }
    head = storage._s3.head_object(
        Bucket=bucket, Key="experimental/job-impl/index.html"
    )
    assert head["ContentType"] == "text/html"


def test_get_latest_report_job_by_model_returns_correct_jobs() -> None:
    """Returns the newest completed report per model, ignoring older, incomplete, and non-report jobs."""
    url = "https://example.com"
    storage.create_job("crawl", url, "claude", JobType.CRAWL)  # ignored: not a report
    storage.create_job("r-claude-old", url, "claude", JobType.REPORT)
    storage.complete_artifact(
        "r-claude-old", ArtifactType.REPORT, "results/r-claude-old/report.md"
    )
    storage.create_job("r-openai", url, "openai", JobType.REPORT)
    storage.complete_artifact(
        "r-openai", ArtifactType.REPORT, "results/r-openai/report.md"
    )
    storage.create_job("r-claude-new", url, "claude", JobType.REPORT)
    storage.complete_artifact(
        "r-claude-new", ArtifactType.REPORT, "results/r-claude-new/report.md"
    )
    storage.create_job("r-claude-pending", url, "claude", JobType.REPORT)  # incomplete

    latest = storage.get_latest_report_job_by_model(url)
    assert latest[ModelName.CLAUDE] == "r-claude-new"
    assert latest[ModelName.OPENAI] == "r-openai"


def test_get_latest_report_job_by_model_returns_none_when_missing() -> None:
    """Returns None for a model with no completed report and for a URL with no reports."""
    url = "https://example.com"
    storage.create_job("r-claude", url, "claude", JobType.REPORT)
    storage.complete_artifact(
        "r-claude", ArtifactType.REPORT, "results/r-claude/report.md"
    )

    latest = storage.get_latest_report_job_by_model(url)
    assert latest[ModelName.CLAUDE] == "r-claude"
    assert latest[ModelName.OPENAI] is None

    assert storage.get_latest_report_job_by_model("https://never.com") == {
        ModelName.CLAUDE: None,
        ModelName.OPENAI: None,
    }
