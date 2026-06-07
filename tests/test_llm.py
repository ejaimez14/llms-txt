from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from agents import WebSearchTool
from src.models import CrawlOutput, SiteMetadata
from src.services.hooks import JobHooks
from src.services.llm import _run_openai, create_agent, run_agent


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


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


def test_create_agent_unsupported_model_raises() -> None:
    with pytest.raises(ValueError):
        create_agent("gpt-4", "crawl", "job-1", "https://example.com", "prompt")


# --- run_agent ---


def test_run_agent_returns_tool_output(mock_client: MagicMock) -> None:
    expected = {"llms_txt": "# Content", "metadata": {}}
    mock_client.messages.create.return_value = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use", name="submit_crawl_results", input=expected
            )
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    assert run_agent(_make_agent_ctx(mock_client), "crawl this") == expected


def test_run_agent_returns_plain_text_on_end_turn(mock_client: MagicMock) -> None:
    mock_client.messages.create.return_value = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="report content")],
        usage=SimpleNamespace(input_tokens=5, output_tokens=10),
    )
    assert (
        run_agent(_make_agent_ctx(mock_client, submit_tool_name=None), "report this")
        == "report content"
    )


def test_run_agent_calls_on_error_and_reraises(mock_client: MagicMock) -> None:
    mock_client.messages.create.side_effect = RuntimeError("timeout")
    ctx = _make_agent_ctx(mock_client)
    with pytest.raises(RuntimeError):
        run_agent(ctx, "crawl this")
    ctx["hooks"].on_error.assert_called_once()


# --- hooks ---


def test_crawl_on_complete_embeds_text(mocker: MockerFixture) -> None:
    mocker.patch(
        "src.services.hooks.save_llms_txt", return_value="s3://bucket/llms.txt"
    )
    mocker.patch("src.services.hooks.upsert_vector")
    mocker.patch("src.services.hooks.upsert_site")
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    mock_embed = mocker.patch("src.services.hooks.embed_text", return_value=[0.1])

    hooks = JobHooks("job-1", "crawl", "https://example.com", "claude")
    hooks.on_start()
    hooks.on_complete(
        {
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
    )

    mock_embed.assert_called_once()


def test_non_crawl_on_complete_does_not_embed(mocker: MockerFixture) -> None:
    mocker.patch(
        "src.services.hooks.save_report", return_value="results/job-1/report.md"
    )
    mocker.patch("src.services.hooks.complete_artifact")
    mocker.patch("src.services.hooks.log_job_event")
    mock_embed = mocker.patch("src.services.hooks.embed_text")

    hooks = JobHooks("job-1", "report", "https://example.com", "claude")
    hooks.on_start()
    hooks.on_complete({"report_markdown": "# Report"})

    mock_embed.assert_not_called()


def test_on_error_maps_agent_type_to_artifact_key(mocker: MockerFixture) -> None:
    mock_fail = mocker.patch("src.services.hooks.fail_artifact")
    mocker.patch("src.services.hooks.log_job_event")

    JobHooks("job-1", "crawl", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_once_with("job-1", "llmsTxt", "boom")

    JobHooks("job-2", "ui-plan", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-2", "plan", "boom")

    JobHooks("job-3", "report", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-3", "report", "boom")

    JobHooks("job-4", "compare", "https://example.com", "claude").on_error(
        RuntimeError("boom")
    )
    mock_fail.assert_called_with("job-4", "comparison", "boom")


# --- codex ---


def test_create_agent_codex_returns_openai_provider() -> None:
    ctx = create_agent("openai", "crawl", "job-1", "https://example.com", "prompt")
    assert ctx["provider"] == "openai"


def test_create_agent_codex_crawl_includes_web_tools() -> None:
    ctx = create_agent("openai", "crawl", "job-1", "https://example.com", "prompt")
    tools = ctx["agent"].tools
    assert len(tools) == 2
    assert any(isinstance(t, WebSearchTool) for t in tools)


def test_create_agent_codex_report_has_no_web_tools() -> None:
    ctx = create_agent("openai", "report", "job-1", "https://example.com", "prompt")
    assert ctx["agent"].tools == []


def test_run_openai_returns_structured_output() -> None:
    crawl_output = CrawlOutput(
        llms_txt="# Site",
        metadata=SiteMetadata(
            tech_stack=[],
            audience=None,
            tone=None,
            business_model=None,
            integrations=[],
            content_types=[],
        ),
    )
    mock_usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    mock_context_wrapper = SimpleNamespace(usage=mock_usage)
    mock_result = SimpleNamespace(
        final_output=crawl_output,
        context_wrapper=mock_context_wrapper,
    )
    mock_hooks = MagicMock()
    ctx = {"provider": "openai", "agent": MagicMock(), "hooks": mock_hooks}

    with patch("src.services.llm.Runner.run_sync", return_value=mock_result):
        output = _run_openai(ctx, "crawl https://example.com")

    assert output == crawl_output.model_dump()
    mock_hooks.on_start.assert_called_once()
    mock_hooks.on_complete.assert_called_once()
