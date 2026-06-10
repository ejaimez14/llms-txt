import json

import pytest
from pytest_mock import MockerFixture

import src.services.recrawl as recrawl_module
from src.constants import AgentType, JobType
from src.services.recrawl import (
    enqueue_compare,
    enqueue_report,
    handle_schedule,
    handle_sqs,
)


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


def _make_typed_sqs_record(body: dict) -> dict:
    """Constructs an SQS record from an arbitrary message body."""
    return {"eventSource": "aws:sqs", "body": json.dumps(body)}


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
    """If trigger_task raises, handle_sqs propagates the exception so SQS retries the message."""
    mocker.patch.object(recrawl_module, "create_job")
    mocker.patch.object(
        recrawl_module, "trigger_task", side_effect=RuntimeError("fargate error")
    )

    records = [_make_sqs_record("https://example.com", "claude")]
    with pytest.raises(RuntimeError, match="fargate error"):
        handle_sqs(_make_sqs_event(records), object())


def test_handle_sqs_report_runs_reporter(mocker: MockerFixture) -> None:
    """A report-typed record dispatches run_reporter with the message fields and skips the crawl path."""
    mock_run_reporter = mocker.patch.object(recrawl_module, "run_reporter")
    mock_trigger = mocker.patch.object(recrawl_module, "trigger_task")

    body = {
        "type": "report",
        "jobId": "job-report",
        "url": "https://example.com",
        "model": "claude",
    }
    handle_sqs(_make_sqs_event([_make_typed_sqs_record(body)]), object())

    mock_run_reporter.assert_called_once_with(
        "job-report", "https://example.com", "claude"
    )
    mock_trigger.assert_not_called()


def test_handle_sqs_compare_runs_comparer(mocker: MockerFixture) -> None:
    """A compare-typed record dispatches run_comparer with the message fields and skips the crawl path."""
    mock_run_comparer = mocker.patch.object(recrawl_module, "run_comparer")
    mock_trigger = mocker.patch.object(recrawl_module, "trigger_task")

    body = {
        "type": "compare",
        "jobId": "job-compare",
        "jobIdA": "rep-claude",
        "jobIdB": "rep-openai",
        "model": "claude",
    }
    handle_sqs(_make_sqs_event([_make_typed_sqs_record(body)]), object())

    mock_run_comparer.assert_called_once_with(
        "job-compare", "rep-claude", "rep-openai", "claude"
    )
    mock_trigger.assert_not_called()


def test_handle_sqs_untyped_record_runs_crawl_path(mocker: MockerFixture) -> None:
    """A record with no type falls through to the crawl path (create_job + two trigger_task calls)."""
    mock_run_reporter = mocker.patch.object(recrawl_module, "run_reporter")
    mock_run_comparer = mocker.patch.object(recrawl_module, "run_comparer")
    mock_trigger = mocker.patch.object(recrawl_module, "trigger_task")
    mocker.patch.object(recrawl_module, "create_job")

    handle_sqs(
        _make_sqs_event([_make_sqs_record("https://example.com", "claude")]), object()
    )

    assert mock_trigger.call_count == 2
    mock_run_reporter.assert_not_called()
    mock_run_comparer.assert_not_called()


def test_enqueue_report_sends_typed_message(mocker: MockerFixture) -> None:
    """enqueue_report sends a report-typed message body to the recrawl queue."""
    mock_sqs = mocker.patch.object(recrawl_module, "_sqs")

    enqueue_report("job-report", "https://example.com", "claude")

    mock_sqs.send_message.assert_called_once()
    body = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert body == {
        "type": "report",
        "jobId": "job-report",
        "url": "https://example.com",
        "model": "claude",
    }


def test_enqueue_compare_sends_typed_message(mocker: MockerFixture) -> None:
    """enqueue_compare sends a compare-typed message body to the recrawl queue."""
    mock_sqs = mocker.patch.object(recrawl_module, "_sqs")

    enqueue_compare("job-compare", "rep-claude", "rep-openai", "claude")

    mock_sqs.send_message.assert_called_once()
    body = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert body == {
        "type": "compare",
        "jobId": "job-compare",
        "jobIdA": "rep-claude",
        "jobIdB": "rep-openai",
        "model": "claude",
    }
