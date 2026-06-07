from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from src.services.hooks import CrawlerClaudeHooks
from src.services.llm import create_agent, run_agent


# --- Fixtures ---


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def crawl_hooks(mocker: MockerFixture) -> CrawlerClaudeHooks:
    mocker.patch(
        "src.services.hooks.save_llms_txt", return_value="s3://bucket/llms.txt"
    )
    mocker.patch("src.services.hooks.embed_text", return_value=[0.1, 0.2, 0.3])
    mocker.patch("src.services.hooks.upsert_vector")
    mocker.patch("src.services.hooks.upsert_site")
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    return CrawlerClaudeHooks("job-123", "crawl", "https://example.com", "claude")


@pytest.fixture()
def ui_plan_hooks(mocker: MockerFixture) -> CrawlerClaudeHooks:
    mocker.patch("src.services.hooks.save_plan", return_value="s3://bucket/plan.md")
    mocker.patch("src.services.hooks.embed_text")
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    return CrawlerClaudeHooks("job-456", "ui-plan", "https://example.com", "claude")


@pytest.fixture()
def report_hooks(mocker: MockerFixture) -> CrawlerClaudeHooks:
    mocker.patch(
        "src.services.hooks.save_report", return_value="results/job-789/report.md"
    )
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    return CrawlerClaudeHooks("job-789", "report", "https://example.com", "claude")


@pytest.fixture()
def compare_hooks(mocker: MockerFixture) -> CrawlerClaudeHooks:
    mocker.patch(
        "src.services.hooks.save_comparison",
        return_value="results/job-101/comparison.md",
    )
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    return CrawlerClaudeHooks("job-101", "compare", "https://example.com", "claude")


def _make_agent_ctx(
    client: MagicMock, submit_tool_name: str | None = "submit_crawl_results"
) -> dict:
    return {
        "provider": "claude",
        "model_id": "claude-haiku-4-5-20251001",
        "client": client,
        "system_prompt": "system",
        "hooks": MagicMock(),
        "tools": [],
        "submit_tool_name": submit_tool_name,
    }


# --- create_agent ---


def test_create_agent_invalid_model_raises() -> None:
    with pytest.raises(ValueError):
        create_agent("gpt-4", "crawl", "job-1", "https://example.com", "prompt")


def test_create_agent_returns_context_dict() -> None:
    ctx = create_agent(
        "claude",
        "crawl",
        "job-1",
        "https://example.com",
        "prompt",
        submit_tool_name="submit_crawl_results",
    )
    assert ctx["provider"] == "claude"
    assert ctx["submit_tool_name"] == "submit_crawl_results"


# --- run_agent ---


def test_run_agent_returns_submit_tool_output(mock_client: MagicMock) -> None:
    expected = {"llms_txt": "# Content", "metadata": {}}
    submit_block = SimpleNamespace(
        type="tool_use", name="submit_crawl_results", input=expected
    )
    mock_client.messages.create.return_value = SimpleNamespace(
        stop_reason="tool_use",
        content=[submit_block],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    assert run_agent(_make_agent_ctx(mock_client), "crawl this") == expected


def test_run_agent_returns_text_on_end_turn(mock_client: MagicMock) -> None:
    mock_client.messages.create.return_value = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="plan content")],
        usage=SimpleNamespace(input_tokens=5, output_tokens=10),
    )
    assert (
        run_agent(_make_agent_ctx(mock_client, submit_tool_name=None), "plan this")
        == "plan content"
    )


def test_run_agent_on_error_calls_hook_and_reraises(mock_client: MagicMock) -> None:
    mock_client.messages.create.side_effect = RuntimeError("timeout")
    ctx = _make_agent_ctx(mock_client)
    with pytest.raises(RuntimeError):
        run_agent(ctx, "crawl this")
    ctx["hooks"].on_error.assert_called_once()


# --- hooks ---


_CRAWL_OUTPUT = {
    "llms_txt": "# Site",
    "metadata": {
        "tech_stack": [],
        "audience": None,
        "tone": None,
        "business_model": None,
        "integrations": [],
        "content_types": [],
    },
}

_UI_PLAN_OUTPUT = {"plan_markdown": "# Plan", "design_tokens": {}}


def test_crawl_on_complete_embeds_upserts_and_completes(
    mocker: MockerFixture, crawl_hooks: CrawlerClaudeHooks
) -> None:
    mock_embed = mocker.patch(
        "src.services.hooks.embed_text", return_value=[0.1, 0.2, 0.3]
    )
    mock_complete = mocker.patch("src.services.hooks.complete_artifact")

    crawl_hooks.on_start()
    crawl_hooks.on_complete(_CRAWL_OUTPUT)

    mock_embed.assert_called_once_with(_CRAWL_OUTPUT["llms_txt"])
    mock_complete.assert_called_once_with(
        "job-123", "llmsTxt", "s3://bucket/llms.txt", 0, 0
    )


def test_ui_plan_on_complete_saves_plan_and_does_not_embed(
    mocker: MockerFixture, ui_plan_hooks: CrawlerClaudeHooks
) -> None:
    mock_save = mocker.patch(
        "src.services.hooks.save_plan", return_value="s3://bucket/plan.md"
    )
    mock_complete = mocker.patch("src.services.hooks.complete_artifact")
    mock_embed = mocker.patch("src.services.hooks.embed_text")

    ui_plan_hooks.on_start()
    ui_plan_hooks.on_complete(_UI_PLAN_OUTPUT)

    mock_save.assert_called_once_with("job-456", "# Plan")
    mock_complete.assert_called_once_with(
        "job-456", "plan", "s3://bucket/plan.md", 0, 0
    )
    mock_embed.assert_not_called()


def test_on_error_fails_correct_artifact(mocker: MockerFixture) -> None:
    mock_fail = mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")

    CrawlerClaudeHooks("job-1", "crawl", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_once_with("job-1", "llmsTxt", "boom")

    CrawlerClaudeHooks("job-2", "ui-plan", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-2", "plan", "boom")


def test_report_on_complete_saves_report_and_does_not_embed(
    mocker: MockerFixture, report_hooks: CrawlerClaudeHooks
) -> None:
    mock_save = mocker.patch(
        "src.services.hooks.save_report", return_value="results/job-789/report.md"
    )
    mock_complete = mocker.patch("src.services.hooks.complete_artifact")
    mock_embed = mocker.patch("src.services.hooks.embed_text")

    report_hooks.on_start()
    report_hooks.on_complete("# Report content")

    mock_save.assert_called_once_with("job-789", "# Report content")
    mock_complete.assert_called_once_with(
        "job-789", "report", "results/job-789/report.md", 0, 0
    )
    mock_embed.assert_not_called()


def test_compare_on_complete_saves_comparison_and_does_not_embed(
    mocker: MockerFixture, compare_hooks: CrawlerClaudeHooks
) -> None:
    mock_save = mocker.patch(
        "src.services.hooks.save_comparison",
        return_value="results/job-101/comparison.md",
    )
    mock_complete = mocker.patch("src.services.hooks.complete_artifact")
    mock_embed = mocker.patch("src.services.hooks.embed_text")

    compare_hooks.on_start()
    compare_hooks.on_complete("# Comparison content")

    mock_save.assert_called_once_with("job-101", "# Comparison content")
    mock_complete.assert_called_once_with(
        "job-101", "comparison", "results/job-101/comparison.md", 0, 0
    )
    mock_embed.assert_not_called()


def test_on_error_fails_correct_artifact_for_report_and_compare(
    mocker: MockerFixture,
) -> None:
    mock_fail = mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")

    CrawlerClaudeHooks("job-r", "report", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-r", "report", "boom")

    CrawlerClaudeHooks("job-c", "compare", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-c", "comparison", "boom")
