import asyncio
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

import src.tasks.base as tasks_base
from src.tasks.base import TaskConfig, run_task
from src.constants import AgentType


def _make_config(mocker: MockerFixture) -> TaskConfig:
    return TaskConfig(
        agent_type=AgentType.CRAWL,
        claude_model="claude-test",
        max_turns=5,
        timeout_seconds=60,
        output_file="out.json",
        output_model=MagicMock(),
        system_prompt="test prompt",
        output_schema_hint="`field` (string)",
        task_instruction="Do the thing: {url}",
    )


def _mock_sdk(mocker: MockerFixture, exc: Exception | None = None) -> None:
    async def _sdk(hooks, url, config):
        if exc:
            raise exc

    mocker.patch.object(tasks_base, "_run_sdk", side_effect=_sdk)


def test_claude_path_calls_hooks_lifecycle(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker)

    run_task("job-1", "https://example.com", "claude", _make_config(mocker))

    mock_hooks.return_value.on_start.assert_called_once()
    mock_hooks.return_value.on_error.assert_not_called()


def test_claude_error_calls_on_error_and_does_not_reraise(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=ValueError("SDK error"))

    run_task("job-1", "https://example.com", "claude", _make_config(mocker))  # must not raise

    mock_hooks.return_value.on_error.assert_called_once()
    mock_hooks.return_value.on_complete.assert_not_called()


def test_claude_timeout_passed_to_on_error(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=asyncio.TimeoutError())

    run_task("job-1", "https://example.com", "claude", _make_config(mocker))

    error_arg = mock_hooks.return_value.on_error.call_args[0][0]
    assert isinstance(error_arg, asyncio.TimeoutError)


def test_openai_path_calls_agent_factory(mocker: MockerFixture) -> None:
    mock_create = mocker.patch.object(tasks_base, "create_agent", return_value={})
    mock_run = mocker.patch.object(tasks_base, "run_agent", return_value={})
    config = _make_config(mocker)

    run_task("job-1", "https://example.com", "openai", config)

    mock_create.assert_called_once_with(
        model="openai",
        agent_type=AgentType.CRAWL,
        job_id="job-1",
        url="https://example.com",
        system_prompt="test prompt",
    )
    mock_run.assert_called_once()
