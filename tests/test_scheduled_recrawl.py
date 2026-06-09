import json
import os
from collections.abc import Generator

import boto3
import pytest
from moto import mock_aws
from pytest_mock import MockerFixture

import src.services.recrawl as recrawl_module
import src.services.storage as storage
from src.constants import JobType
from src.services.recrawl import handle_schedule, handle_sqs


def _make_sqs_record(url: str, model: str) -> dict:
    """Constructs a realistic SQS event record for a given URL and model."""
    return {
        "eventSource": "aws:sqs",
        "body": json.dumps({"url": url, "model": model}),
    }


def _make_sqs_event(records: list[dict]) -> dict:
    """Wraps a list of SQS records into a Lambda SQS event."""
    return {"Records": records}


def _make_eventbridge_event() -> dict:
    """Constructs a realistic EventBridge scheduled-event payload."""
    return {"source": "aws.events", "detail-type": "Scheduled Event"}


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

        sqs_client = boto3.client("sqs", region_name="us-east-1")
        sqs_client.create_queue(QueueName="test-recrawl")
        recrawl_module._sqs = boto3.client("sqs", region_name="us-east-1")

        yield


def test_handle_schedule_enqueues_one_message_per_url() -> None:
    """N sites in the sites table results in N SQS messages with correct MessageBody structure."""
    metadata: dict = {"tech_stack": [], "integrations": [], "content_types": []}
    storage.upsert_site(
        "https://alpha.com", "job-a", "results/job-a/llms.txt", metadata, "claude"
    )
    storage.upsert_site(
        "https://beta.com", "job-b", "results/job-b/llms.txt", metadata, "claude"
    )

    result = handle_schedule(_make_eventbridge_event(), object())

    sqs_client = boto3.client("sqs", region_name="us-east-1")
    queue_url = os.environ["RECRAWL_QUEUE_URL"]
    messages = sqs_client.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10
    ).get("Messages", [])

    assert len(messages) == 2
    enqueued_urls = {json.loads(m["Body"])["url"] for m in messages}
    assert "https://alpha.com" in enqueued_urls
    assert "https://beta.com" in enqueued_urls
    for message in messages:
        body = json.loads(message["Body"])
        assert "url" in body
        assert "model" in body

    assert result["scheduled"] == 2


def test_handle_schedule_returns_count() -> None:
    """Return dict contains scheduled key equal to the number of sites."""
    metadata: dict = {"tech_stack": [], "integrations": [], "content_types": []}
    storage.upsert_site(
        "https://example.com", "job-1", "results/job-1/llms.txt", metadata, "claude"
    )

    result = handle_schedule(_make_eventbridge_event(), object())

    assert result == {"scheduled": 1}


def test_handle_sqs_creates_new_job_id(mocker: MockerFixture) -> None:
    """Each SQS record creates a new unique job via create_job - old records are not overwritten."""
    mocker.patch.object(recrawl_module, "trigger_task")
    mock_create_job = mocker.patch.object(recrawl_module, "create_job")

    records = [
        _make_sqs_record("https://alpha.com", "claude"),
        _make_sqs_record("https://beta.com", "claude"),
    ]
    handle_sqs(_make_sqs_event(records), object())

    assert mock_create_job.call_count == 2
    job_ids = [call.args[0] for call in mock_create_job.call_args_list]
    assert job_ids[0] != job_ids[1], "Each SQS record must produce a distinct job_id"
    for call in mock_create_job.call_args_list:
        assert call.args[3] == JobType.CRAWL


def test_handle_sqs_runs_both_agents(mocker: MockerFixture) -> None:
    """Both CRAWL and UI_PLAN trigger_task calls are fired for each SQS record."""
    mock_trigger = mocker.patch.object(recrawl_module, "trigger_task")
    mocker.patch.object(recrawl_module, "create_job")

    records = [_make_sqs_record("https://example.com", "claude")]
    handle_sqs(_make_sqs_event(records), object())

    assert mock_trigger.call_count == 2
    agent_types = {call.args[0] for call in mock_trigger.call_args_list}
    from src.constants import AgentType
    assert AgentType.CRAWL in agent_types
    assert AgentType.UI_PLAN in agent_types


def test_handle_sqs_raises_on_agent_failure(mocker: MockerFixture) -> None:
    """If trigger_task raises, handle_sqs propagates the exception so SQS retries the message."""
    mocker.patch.object(recrawl_module, "create_job")
    mocker.patch.object(
        recrawl_module, "trigger_task", side_effect=RuntimeError("fargate error")
    )

    records = [_make_sqs_record("https://example.com", "claude")]
    with pytest.raises(RuntimeError, match="fargate error"):
        handle_sqs(_make_sqs_event(records), object())
