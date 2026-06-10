import os
import time
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

import src.services.hooks as hooks_module
import src.tasks.base as tasks_base
from src.constants import (
    AgentType,
    IMPLEMENTER_BASE_BRANCH,
    IMPLEMENTER_REPO,
)
from src.services.hooks import JobHooks
from src.tasks.base import _build_implement_prompt, run_task
from src.tasks.registry import REGISTRY


@pytest.fixture
def mock_get_artifact_content(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        tasks_base, "get_artifact_content", return_value="## UI Plan\n..."
    )


@pytest.fixture
def mock_run_sdk(mocker: MockerFixture) -> MagicMock:
    async def _noop(hooks, url, config):
        pass

    return mocker.patch.object(tasks_base, "_run_sdk", side_effect=_noop)


def test_implement_config_registered() -> None:
    config = REGISTRY.get(AgentType.IMPLEMENT)
    assert config.agent_type == AgentType.IMPLEMENT
    assert config.output_file == "implement-output.json"
    assert "Read" in config.allowed_tools
    assert "Bash" in config.allowed_tools


def test_run_task_implement_calls_hooks_lifecycle(
    mocker: MockerFixture,
    mock_run_sdk: MagicMock,
) -> None:
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    config = REGISTRY.get(AgentType.IMPLEMENT)

    run_task("job-1", "source-job-1", "claude", config)

    mock_hooks.return_value.on_start.assert_called_once()
    mock_hooks.return_value.on_error.assert_not_called()


def test_run_task_implement_calls_on_error_on_failure(
    mocker: MockerFixture,
) -> None:
    async def _raise(hooks, url, config):
        raise RuntimeError("SDK boom")

    mocker.patch.object(tasks_base, "_run_sdk", side_effect=_raise)
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    config = REGISTRY.get(AgentType.IMPLEMENT)

    with pytest.raises(RuntimeError, match="SDK boom"):
        run_task("job-2", "source-job-2", "claude", config)

    mock_hooks.return_value.on_error.assert_called_once()
    mock_hooks.return_value.on_complete.assert_not_called()


def test_build_implement_prompt_raises_when_plan_unavailable(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(tasks_base, "get_artifact_content", return_value=None)
    config = REGISTRY.get(AgentType.IMPLEMENT)

    with pytest.raises(
        ValueError, match="UI plan artifact unavailable for url source-job-3"
    ):
        _build_implement_prompt("source-job-3", config)


def test_build_implement_prompt_includes_plan_and_repo(
    mock_get_artifact_content: MagicMock,
) -> None:
    os.environ["AGENT_ID"] = "abcdef12345678"
    config = REGISTRY.get(AgentType.IMPLEMENT)

    prompt = _build_implement_prompt("source-job-4", config)

    assert "## UI Plan" in prompt
    assert IMPLEMENTER_REPO in prompt
    assert IMPLEMENTER_BASE_BRANCH in prompt
    assert "ui-implement/abcdef12" in prompt
    assert "implement-output.json" in prompt
    assert '"pr_url"' in prompt


def test_build_implement_prompt_missing_plan_triggers_on_error(
    mocker: MockerFixture,
) -> None:
    """Verifies run_task calls on_error and re-raises when _build_implement_prompt raises ValueError."""
    mocker.patch.object(tasks_base, "get_artifact_content", return_value=None)
    mock_hooks = mocker.patch.object(tasks_base, "JobHooks", return_value=MagicMock())
    config = REGISTRY.get(AgentType.IMPLEMENT)

    with pytest.raises(ValueError, match="source-job-5"):
        run_task("job-5", "source-job-5", "claude", config)

    mock_hooks.return_value.on_error.assert_called_once()
    error_arg = mock_hooks.return_value.on_error.call_args[0][0]
    assert isinstance(error_arg, ValueError)
    assert "source-job-5" in str(error_arg)


def test_hooks_on_complete_implement_saves_pr_url(mocker: MockerFixture) -> None:
    mock_store = mocker.patch.object(hooks_module, "store_implement_result")
    hooks = JobHooks("job-6", AgentType.IMPLEMENT, "owner/repo", "claude")
    hooks._start_time = time.time()

    hooks.on_complete({"pr_url": "https://github.com/owner/repo/pull/42"})

    mock_store.assert_called_once_with("job-6", "https://github.com/owner/repo/pull/42")
