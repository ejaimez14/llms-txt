import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

import src.tasks.base as tasks_base
from src.constants import AgentType
from src.models import TaskConfig
from src.tasks.base import run_task


def _make_config(agent_type: AgentType = AgentType.CRAWL) -> TaskConfig:
    return TaskConfig(
        agent_type=agent_type,
        claude_model="claude-test",
        max_turns=5,
        timeout_seconds=60,
        output_file="out.json",
        output_model=MagicMock(),
        system_prompt="test prompt",
        output_schema_hint="`field` (string)",
        task_instruction="Do the thing: {url}",
        allowed_tools=["WebFetch", "Write"],
    )


def _mock_sdk(mocker: MockerFixture, exc: Exception | None = None) -> AsyncMock:
    mock = mocker.patch.object(tasks_base, "_run_sdk", new_callable=AsyncMock)
    if exc:
        mock.side_effect = exc
    return mock


# --- Crawl / ui-plan: both models route through llm.py ---


@pytest.mark.parametrize("model", ["claude", "openai"])
def test_crawl_routes_to_create_agent(mocker: MockerFixture, model: str) -> None:
    mock_create = mocker.patch.object(tasks_base, "create_agent", return_value={})
    mock_run = mocker.patch.object(tasks_base, "run_agent")

    run_task("job-1", "https://example.com", model, _make_config(AgentType.CRAWL))

    mock_create.assert_called_once_with(
        model, AgentType.CRAWL, "job-1", "https://example.com", "test prompt",
        max_turns=5, timeout_seconds=60,
    )
    mock_run.assert_called_once_with({}, "Do the thing: https://example.com")


def test_ui_plan_routes_to_create_agent(mocker: MockerFixture) -> None:
    mock_create = mocker.patch.object(tasks_base, "create_agent", return_value={})
    mocker.patch.object(tasks_base, "run_agent")

    run_task("job-1", "https://example.com", "claude", _make_config(AgentType.UI_PLAN))

    mock_create.assert_called_once_with(
        "claude", AgentType.UI_PLAN, "job-1", "https://example.com", "test prompt",
        max_turns=5, timeout_seconds=60,
    )


# --- Implement: always routes to Claude Code CLI SDK ---


def test_implement_routes_to_sdk(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker)

    run_task("job-1", "https://example.com", "claude", _make_config(AgentType.IMPLEMENT))

    mock_hooks.return_value.on_start.assert_called_once()
    mock_hooks.return_value.on_error.assert_not_called()


def test_implement_error_calls_on_error_and_reraises(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=ValueError("sdk failed"))

    with pytest.raises(ValueError, match="sdk failed"):
        run_task("job-1", "https://example.com", "claude", _make_config(AgentType.IMPLEMENT))

    mock_hooks.return_value.on_error.assert_called_once()
    mock_hooks.return_value.on_complete.assert_not_called()


def test_implement_timeout_calls_on_error(mocker: MockerFixture) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    _mock_sdk(mocker, exc=asyncio.TimeoutError())

    with pytest.raises(asyncio.TimeoutError):
        run_task("job-1", "https://example.com", "claude", _make_config(AgentType.IMPLEMENT))

    error_arg = mock_hooks.return_value.on_error.call_args[0][0]
    assert isinstance(error_arg, asyncio.TimeoutError)
