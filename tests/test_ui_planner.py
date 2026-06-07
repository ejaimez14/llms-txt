from pytest_mock import MockerFixture

import src.agents.ui_planner as ui_planner_module
from src.agents.ui_planner import run_ui_planner


def test_run_ui_planner_passes_correct_params(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("src.agents.ui_planner.create_agent", return_value={})
    mocker.patch("src.agents.ui_planner.run_agent", return_value={})

    run_ui_planner("job-1", "https://example.com", "claude")

    mock_create.assert_called_once_with(
        model="claude",
        agent_type="ui-plan",
        job_id="job-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )


def test_run_ui_planner_returns_run_agent_output(mocker: MockerFixture) -> None:
    expected = {"plan_markdown": "# Plan", "design_tokens": {}}
    mocker.patch("src.agents.ui_planner.create_agent", return_value={})
    mocker.patch("src.agents.ui_planner.run_agent", return_value=expected)

    result = run_ui_planner("job-1", "https://example.com", "claude")

    assert result == expected


def test_ui_planner_no_direct_storage_calls() -> None:
    assert not hasattr(ui_planner_module, "storage")
    assert not hasattr(ui_planner_module, "embed_text")
    assert not hasattr(ui_planner_module, "upsert_vector")
