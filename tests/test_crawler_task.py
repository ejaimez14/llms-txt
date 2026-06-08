import asyncio
import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from src.tasks.crawler import run_crawler_task


def _make_crawl_output_json() -> str:
    return json.dumps(
        {
            "llms_txt": "# Example\n> A test site\n",
            "metadata": {
                "tech_stack": ["Python"],
                "audience": "developers",
                "tone": "technical",
                "business_model": "SaaS",
                "integrations": [],
                "content_types": ["docs"],
            },
        }
    )


def test_run_crawler_task_openai_calls_agent_factory(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("src.tasks.crawler.create_agent", return_value={})
    mock_run = mocker.patch("src.tasks.crawler.run_agent", return_value={})

    run_crawler_task("job-1", "https://example.com", "openai")

    mock_create.assert_called_once_with(
        model="openai",
        agent_type="crawl",
        job_id="job-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )
    mock_run.assert_called_once()


def test_run_crawler_task_claude_calls_hooks_on_success(mocker: MockerFixture) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.crawler.JobHooks", return_value=mock_hooks)

    crawl_json = _make_crawl_output_json()

    async def fake_run_sdk(hooks, url):
        output_data = json.loads(crawl_json)
        hooks.on_complete(output_data)

    mocker.patch("src.tasks.crawler._run_sdk", side_effect=fake_run_sdk)

    run_crawler_task("job-1", "https://example.com", "claude")

    mock_hooks.on_start.assert_called_once()
    mock_hooks.on_complete.assert_called_once()
    mock_hooks.on_error.assert_not_called()


def test_run_crawler_task_claude_calls_hooks_on_error(mocker: MockerFixture) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.crawler.JobHooks", return_value=mock_hooks)

    async def fail_sdk(hooks, url):
        raise ValueError("SDK error")

    mocker.patch("src.tasks.crawler._run_sdk", side_effect=fail_sdk)

    # Should not re-raise
    run_crawler_task("job-1", "https://example.com", "claude")

    mock_hooks.on_start.assert_called_once()
    mock_hooks.on_error.assert_called_once()
    mock_hooks.on_complete.assert_not_called()


def test_run_crawler_task_claude_does_not_reraise(mocker: MockerFixture) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.crawler.JobHooks", return_value=mock_hooks)

    async def fail_sdk(hooks, url):
        raise RuntimeError("timeout")

    mocker.patch("src.tasks.crawler._run_sdk", side_effect=fail_sdk)

    # Must not raise
    run_crawler_task("job-1", "https://example.com", "claude")


def test_run_crawler_task_claude_hooks_on_error_on_timeout(
    mocker: MockerFixture,
) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.crawler.JobHooks", return_value=mock_hooks)

    async def timeout_sdk(hooks, url):
        raise asyncio.TimeoutError()

    mocker.patch("src.tasks.crawler._run_sdk", side_effect=timeout_sdk)

    run_crawler_task("job-1", "https://example.com", "claude")

    mock_hooks.on_error.assert_called_once()
    error_arg = mock_hooks.on_error.call_args[0][0]
    assert isinstance(error_arg, asyncio.TimeoutError)
