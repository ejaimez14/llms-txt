from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

import src.services.fargate as fargate_module
from src.constants import AgentType
from src.services.fargate import trigger_task


@pytest.fixture
def mock_ecs(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(fargate_module, "_ecs", autospec=True)


def _get_container_override(mock_ecs: MagicMock) -> dict:
    return mock_ecs.run_task.call_args[1]["overrides"]["containerOverrides"][0]


def test_trigger_task_uses_shared_task_definition(mock_ecs: MagicMock) -> None:
    trigger_task(AgentType.CRAWL, "job-1", "https://example.com", "claude")

    call_kwargs = mock_ecs.run_task.call_args[1]
    assert call_kwargs["cluster"] == "test-cluster"
    assert "test-agent" in call_kwargs["taskDefinition"]
    assert call_kwargs["launchType"] == "FARGATE"
    assert (
        "sg-test"
        in call_kwargs["networkConfiguration"]["awsvpcConfiguration"]["securityGroups"]
    )


def test_trigger_task_passes_agent_type_and_env(mock_ecs: MagicMock) -> None:
    trigger_task(AgentType.CRAWL, "job-42", "https://example.com", "openai")

    override = _get_container_override(mock_ecs)
    assert override["command"] == ["python", "-m", "src.tasks"]
    env_map = {item["name"]: item["value"] for item in override["environment"]}
    assert env_map["AGENT_TYPE"] == "crawl"
    assert env_map["AGENT_ID"] == "job-42"
    assert env_map["AGENT_URL"] == "https://example.com"
    assert env_map["AGENT_MODEL"] == "openai"


def test_trigger_task_ui_plan_sets_correct_agent_type(mock_ecs: MagicMock) -> None:
    trigger_task(AgentType.UI_PLAN, "job-1", "https://example.com", "claude")

    override = _get_container_override(mock_ecs)
    env_map = {item["name"]: item["value"] for item in override["environment"]}
    assert env_map["AGENT_TYPE"] == "ui-plan"


def test_trigger_task_implement_uses_implement_task_definition(
    mock_ecs: MagicMock,
) -> None:
    trigger_task(AgentType.IMPLEMENT, "job-1", "parent-job-id", "claude")

    call_kwargs = mock_ecs.run_task.call_args[1]
    assert "test-implement" in call_kwargs["taskDefinition"]


def test_trigger_task_non_implement_uses_shared_task_definition(
    mock_ecs: MagicMock,
) -> None:
    trigger_task(AgentType.CRAWL, "job-1", "https://example.com", "claude")

    call_kwargs = mock_ecs.run_task.call_args[1]
    assert "test-agent" in call_kwargs["taskDefinition"]
    assert "implement" not in call_kwargs["taskDefinition"]


def test_trigger_task_reraises_on_error(mock_ecs: MagicMock) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_task(AgentType.CRAWL, "job-1", "https://example.com", "claude")
