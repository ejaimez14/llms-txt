from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

import src.services.fargate as fargate_module
from src.constants import (
    CRAWLER_TASK_COMMAND,
    IMPLEMENTER_TASK_COMMAND,
    UI_PLANNER_TASK_COMMAND,
)
from src.services.fargate import (
    trigger_crawler_task,
    trigger_implementer_task,
    trigger_ui_planner_task,
)


@pytest.fixture
def mock_ecs(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(fargate_module, "_ecs", autospec=True)


def _get_container_override(mock_ecs: MagicMock) -> dict:
    call_kwargs = mock_ecs.run_task.call_args[1]
    return call_kwargs["overrides"]["containerOverrides"][0]


def test_trigger_crawler_task_uses_shared_task_definition(mock_ecs) -> None:
    trigger_crawler_task("job-1", "https://example.com", "claude")

    call_kwargs = mock_ecs.run_task.call_args[1]
    assert call_kwargs["cluster"] == "test-cluster"
    assert "test-agent" in call_kwargs["taskDefinition"]
    assert call_kwargs["launchType"] == "FARGATE"
    assert "sg-test" in call_kwargs["networkConfiguration"]["awsvpcConfiguration"]["securityGroups"]


def test_trigger_crawler_task_passes_command_and_env(mock_ecs) -> None:
    trigger_crawler_task("job-42", "https://example.com", "openai")

    override = _get_container_override(mock_ecs)
    assert override["name"] == "agent"
    assert override["command"] == CRAWLER_TASK_COMMAND
    env_map = {item["name"]: item["value"] for item in override["environment"]}
    assert env_map["CRAWLER_JOB_ID"] == "job-42"
    assert env_map["CRAWLER_URL"] == "https://example.com"
    assert env_map["CRAWLER_MODEL"] == "openai"


def test_trigger_crawler_task_reraises_on_error(mock_ecs) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_crawler_task("job-1", "https://example.com", "claude")


def test_trigger_ui_planner_task_passes_command_and_env(mock_ecs) -> None:
    trigger_ui_planner_task("job-42", "https://example.com", "openai")

    override = _get_container_override(mock_ecs)
    assert override["name"] == "agent"
    assert override["command"] == UI_PLANNER_TASK_COMMAND
    env_map = {item["name"]: item["value"] for item in override["environment"]}
    assert env_map["UI_PLANNER_JOB_ID"] == "job-42"
    assert env_map["UI_PLANNER_URL"] == "https://example.com"
    assert env_map["UI_PLANNER_MODEL"] == "openai"


def test_trigger_ui_planner_task_reraises_on_error(mock_ecs) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_ui_planner_task("job-1", "https://example.com", "claude")


def test_trigger_implementer_task_passes_command_and_env(mock_ecs) -> None:
    trigger_implementer_task("job-42", "https://example.com", "claude")

    override = _get_container_override(mock_ecs)
    assert override["name"] == "agent"
    assert override["command"] == IMPLEMENTER_TASK_COMMAND
    env_map = {item["name"]: item["value"] for item in override["environment"]}
    assert env_map["IMPLEMENTER_JOB_ID"] == "job-42"
    assert env_map["IMPLEMENTER_URL"] == "https://example.com"
    assert env_map["IMPLEMENTER_MODEL"] == "claude"


def test_trigger_implementer_task_reraises_on_error(mock_ecs) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_implementer_task("job-1", "https://example.com", "claude")
