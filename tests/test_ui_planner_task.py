import asyncio
import json
from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from src.tasks.ui_planner import run_ui_planner_task


def _make_ui_plan_output_json() -> str:
    return json.dumps(
        {
            "plan_markdown": "# UI Plan\n## Design Tokens\n",
            "design_tokens": {
                "primary_color": "#3B82F6",
                "secondary_color": None,
                "background_color": "#FFFFFF",
                "heading_font": "Inter",
                "body_font": "Inter",
                "css_framework": "Tailwind",
            },
        }
    )


def test_run_ui_planner_task_openai_calls_agent_factory(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("src.tasks.ui_planner.create_agent", return_value={})
    mock_run = mocker.patch("src.tasks.ui_planner.run_agent", return_value={})

    run_ui_planner_task("job-1", "https://example.com", "openai")

    mock_create.assert_called_once_with(
        model="openai",
        agent_type="ui-plan",
        job_id="job-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )
    mock_run.assert_called_once()


def test_run_ui_planner_task_claude_calls_hooks_on_success(
    mocker: MockerFixture,
) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.ui_planner.JobHooks", return_value=mock_hooks)

    plan_json = _make_ui_plan_output_json()

    async def fake_run_sdk(hooks, url):
        output_data = json.loads(plan_json)
        hooks.on_complete(output_data)

    mocker.patch("src.tasks.ui_planner._run_sdk", side_effect=fake_run_sdk)

    run_ui_planner_task("job-1", "https://example.com", "claude")

    mock_hooks.on_start.assert_called_once()
    mock_hooks.on_complete.assert_called_once()
    mock_hooks.on_error.assert_not_called()


def test_run_ui_planner_task_claude_calls_hooks_on_error(mocker: MockerFixture) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.ui_planner.JobHooks", return_value=mock_hooks)

    async def fail_sdk(hooks, url):
        raise ValueError("SDK error")

    mocker.patch("src.tasks.ui_planner._run_sdk", side_effect=fail_sdk)

    # Should not re-raise
    run_ui_planner_task("job-1", "https://example.com", "claude")

    mock_hooks.on_start.assert_called_once()
    mock_hooks.on_error.assert_called_once()
    mock_hooks.on_complete.assert_not_called()


def test_run_ui_planner_task_claude_does_not_reraise(mocker: MockerFixture) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.ui_planner.JobHooks", return_value=mock_hooks)

    async def fail_sdk(hooks, url):
        raise RuntimeError("missing output file")

    mocker.patch("src.tasks.ui_planner._run_sdk", side_effect=fail_sdk)

    # Must not raise
    run_ui_planner_task("job-1", "https://example.com", "claude")


def test_run_ui_planner_task_claude_hooks_on_error_on_timeout(
    mocker: MockerFixture,
) -> None:
    mock_hooks = MagicMock()
    mocker.patch("src.tasks.ui_planner.JobHooks", return_value=mock_hooks)

    async def timeout_sdk(hooks, url):
        raise asyncio.TimeoutError()

    mocker.patch("src.tasks.ui_planner._run_sdk", side_effect=timeout_sdk)

    run_ui_planner_task("job-1", "https://example.com", "claude")

    mock_hooks.on_error.assert_called_once()
    error_arg = mock_hooks.on_error.call_args[0][0]
    assert isinstance(error_arg, asyncio.TimeoutError)
