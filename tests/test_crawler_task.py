import asyncio
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from src.tasks.crawler import run_crawler_task


def _mock_sdk(mocker: MockerFixture, exc: Exception | None = None) -> None:
    async def _sdk(hooks, url):
        if exc:
            raise exc

    mocker.patch("src.tasks.crawler._run_sdk", side_effect=_sdk)


def test_openai_path_calls_agent_factory(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("src.tasks.crawler.create_agent", return_value={})
    mock_run = mocker.patch("src.tasks.crawler.run_agent", return_value={})

    run_crawler_task("job-1", "https://example.com", "openai")

    mock_create.assert_called_once_with(
        model="openai",
        agent_type=mocker.ANY,
        job_id="job-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )
    mock_run.assert_called_once()


def test_claude_success_path_calls_hooks(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch("src.tasks.crawler.JobHooks", return_value=MagicMock())
    _mock_sdk(mocker)

    run_crawler_task("job-1", "https://example.com", "claude")

    mock_hooks.return_value.on_start.assert_called_once()
    mock_hooks.return_value.on_error.assert_not_called()


def test_claude_error_path_calls_on_error_and_does_not_reraise(
    mocker: MockerFixture,
) -> None:
    mock_hooks = mocker.patch("src.tasks.crawler.JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=ValueError("SDK error"))

    run_crawler_task("job-1", "https://example.com", "claude")  # must not raise

    mock_hooks.return_value.on_error.assert_called_once()
    mock_hooks.return_value.on_complete.assert_not_called()


def test_claude_timeout_passed_to_on_error(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch("src.tasks.crawler.JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=asyncio.TimeoutError())

    run_crawler_task("job-1", "https://example.com", "claude")

    error_arg = mock_hooks.return_value.on_error.call_args[0][0]
    assert isinstance(error_arg, asyncio.TimeoutError)
