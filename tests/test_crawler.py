import src.agents.crawler as crawler_module
from pytest_mock import MockerFixture

from src.agents.crawler import run_crawler


def test_run_crawler_dispatches_fargate_for_claude(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.crawler.trigger_crawler_task")

    run_crawler("job-1", "https://example.com", "claude")

    mock_trigger.assert_called_once_with("job-1", "https://example.com", "claude")


def test_run_crawler_dispatches_fargate_for_openai(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.crawler.trigger_crawler_task")

    run_crawler("job-2", "https://example.com", "openai")

    mock_trigger.assert_called_once_with("job-2", "https://example.com", "openai")


def test_run_crawler_dispatches_fargate_for_all_models(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.crawler.trigger_crawler_task")

    for model in ("claude", "openai"):
        run_crawler("job-1", "https://example.com", model)

    assert mock_trigger.call_count == 2
    assert not hasattr(crawler_module, "run_agent")
    assert not hasattr(crawler_module, "create_agent")


def test_crawler_no_direct_storage_calls() -> None:
    assert not hasattr(crawler_module, "save_llms_txt")
    assert not hasattr(crawler_module, "embed_text")
    assert not hasattr(crawler_module, "upsert_vector")
