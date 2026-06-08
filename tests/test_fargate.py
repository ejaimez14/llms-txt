import pytest
from pytest_mock import MockerFixture

import src.services.fargate as fargate_module
from src.services.fargate import (
    trigger_crawler_task,
    trigger_implementer_task,
    trigger_ui_planner_task,
)


@pytest.fixture
def mock_ecs(mocker: MockerFixture):
    return mocker.patch.object(fargate_module, "_ecs", autospec=True)


def test_trigger_crawler_task_calls_run_task(mock_ecs) -> None:
    trigger_crawler_task("job-1", "https://example.com", "claude")

    mock_ecs.run_task.assert_called_once()
    call_kwargs = mock_ecs.run_task.call_args[1]
    assert call_kwargs["cluster"] == "test-cluster"
    assert "test-crawler" in call_kwargs["taskDefinition"]
    assert call_kwargs["launchType"] == "FARGATE"
    vpc_config = call_kwargs["networkConfiguration"]["awsvpcConfiguration"]
    assert "sg-test" in vpc_config["securityGroups"]


def test_trigger_crawler_task_passes_env_overrides(mock_ecs) -> None:
    trigger_crawler_task("job-42", "https://example.com", "openai")

    call_kwargs = mock_ecs.run_task.call_args[1]
    container_env = call_kwargs["overrides"]["containerOverrides"][0]["environment"]
    env_map = {item["name"]: item["value"] for item in container_env}

    assert env_map["CRAWLER_JOB_ID"] == "job-42"
    assert env_map["CRAWLER_URL"] == "https://example.com"
    assert env_map["CRAWLER_MODEL"] == "openai"


def test_trigger_crawler_task_reraises_on_error(mock_ecs) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_crawler_task("job-1", "https://example.com", "claude")


def test_trigger_ui_planner_task_calls_run_task(mock_ecs) -> None:
    trigger_ui_planner_task("job-1", "https://example.com", "claude")

    mock_ecs.run_task.assert_called_once()
    call_kwargs = mock_ecs.run_task.call_args[1]
    assert call_kwargs["cluster"] == "test-cluster"
    assert "test-ui-planner" in call_kwargs["taskDefinition"]
    assert call_kwargs["launchType"] == "FARGATE"
    vpc_config = call_kwargs["networkConfiguration"]["awsvpcConfiguration"]
    assert "sg-test" in vpc_config["securityGroups"]


def test_trigger_ui_planner_task_passes_env_overrides(mock_ecs) -> None:
    trigger_ui_planner_task("job-42", "https://example.com", "openai")

    call_kwargs = mock_ecs.run_task.call_args[1]
    container_env = call_kwargs["overrides"]["containerOverrides"][0]["environment"]
    env_map = {item["name"]: item["value"] for item in container_env}

    assert env_map["UI_PLANNER_JOB_ID"] == "job-42"
    assert env_map["UI_PLANNER_URL"] == "https://example.com"
    assert env_map["UI_PLANNER_MODEL"] == "openai"


def test_trigger_ui_planner_task_reraises_on_error(mock_ecs) -> None:
    mock_ecs.run_task.side_effect = RuntimeError("AWS error")

    with pytest.raises(RuntimeError, match="AWS error"):
        trigger_ui_planner_task("job-1", "https://example.com", "claude")


def test_trigger_implementer_task_calls_run_task(mock_ecs) -> None:
    trigger_implementer_task("job-1", "https://example.com", "claude")

    mock_ecs.run_task.assert_called_once()
    call_kwargs = mock_ecs.run_task.call_args[1]
    assert call_kwargs["cluster"] == "test-cluster"
    assert "test-implementer" in call_kwargs["taskDefinition"]
