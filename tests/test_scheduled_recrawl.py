import json

import pytest
from pytest_mock import MockerFixture

import src.services.recrawl as recrawl_module
from src.constants import AgentType, JobType
from src.services.recrawl import handle_schedule, handle_sqs


def _make_site(url: str) -> dict:
    """Minimal site record as returned by list_sites."""
    return {"url": url, "model": "claude"}


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


def test_handle_schedule_enqueues_one_message_per_url(mocker: MockerFixture) -> None:
    """N sites returned by list_sites results in N SQS send_message calls with correct body structure."""
    mocker.patch.object(
        recrawl_module,
        "list_sites",
        return_value=[_make_site("https://alpha.com"), _make_site("https://beta.com")],
    )
    mock_sqs = mocker.patch.object(recrawl_module, "_sqs")

    handle_schedule(_make_eventbridge_event(), object())

    assert mock_sqs.send_message.call_count == 2
    bodies = [
        json.loads(c.kwargs["MessageBody"])
        for c in mock_sqs.send_message.call_args_list
    ]
    assert {b["url"] for b in bodies} == {"https://alpha.com", "https://beta.com"}
    for body in bodies:
        assert "url" in body
        assert "model" in body


def test_handle_schedule_returns_count(mocker: MockerFixture) -> None:
    """Return dict contains scheduled key equal to the number of sites."""
    mocker.patch.object(
        recrawl_module, "list_sites", return_value=[_make_site("https://example.com")]
    )
    mocker.patch.object(recrawl_module, "_sqs")

    result = handle_schedule(_make_eventbridge_event(), object())

    assert result == {"scheduled": 1}


def test_handle_sqs_creates_new_job_id(mocker: MockerFixture) -> None:
    """Each SQS record creates a new unique job via create_job — old records are not overwritten."""
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
    assert AgentType.CRAWL in agent_types
    assert AgentType.UI_PLAN in agent_types


def test_handle_sqs_raises_on_agent_failure(mocker: MockerFixture) -> None:
    """If trigger_task raises, handle_sqs fails both artifacts and propagates so SQS retries."""
    mocker.patch.object(recrawl_module, "create_job")
    mock_fail = mocker.patch.object(recrawl_module, "fail_artifact")
    mocker.patch.object(
        recrawl_module, "trigger_task", side_effect=RuntimeError("fargate error")
    )

    records = [_make_sqs_record("https://example.com", "claude")]
    with pytest.raises(RuntimeError, match="fargate error"):
        handle_sqs(_make_sqs_event(records), object())

    assert mock_fail.call_count == 2
