import src.agents.ui_planner as ui_planner_module
from pytest_mock import MockerFixture

from src.agents.ui_planner import run_ui_planner


def test_run_ui_planner_dispatches_fargate_for_claude(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.ui_planner.trigger_ui_planner_task")

    run_ui_planner("job-1", "https://example.com", "claude")

    mock_trigger.assert_called_once_with("job-1", "https://example.com", "claude")


def test_run_ui_planner_dispatches_fargate_for_openai(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.ui_planner.trigger_ui_planner_task")

    run_ui_planner("job-2", "https://example.com", "openai")

    mock_trigger.assert_called_once_with("job-2", "https://example.com", "openai")


def test_run_ui_planner_dispatches_fargate_for_all_models(mocker: MockerFixture) -> None:
    mock_trigger = mocker.patch("src.agents.ui_planner.trigger_ui_planner_task")

    for model in ("claude", "openai"):
        run_ui_planner("job-1", "https://example.com", model)

    assert mock_trigger.call_count == 2
    assert not hasattr(ui_planner_module, "run_agent")
    assert not hasattr(ui_planner_module, "create_agent")


def test_ui_planner_no_direct_storage_calls() -> None:
    assert not hasattr(ui_planner_module, "storage")
    assert not hasattr(ui_planner_module, "embed_text")
    assert not hasattr(ui_planner_module, "upsert_vector")
