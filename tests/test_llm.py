from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from agents import WebSearchTool
from src.models import CrawlOutput, SiteMetadata
from src.services.hooks import JobHooks
from src.services.llm import _run_openai, create_agent, run_agent


def _make_claude_ctx(response_model=CrawlOutput, extra_tools=None) -> dict:
    return {
        "provider": "claude",
        "model_id": "claude-haiku-4-5-20251001",
        "system_prompt": "system",
        "hooks": MagicMock(),
        "response_model": response_model,
        "extra_tools": extra_tools or [],
    }


# --- create_agent ---


def test_create_agent_unsupported_model_raises() -> None:
    with pytest.raises(ValueError):
        create_agent("gpt-4", "crawl", "job-1", "https://example.com", "prompt")


def test_create_agent_unknown_agent_type_raises() -> None:
    with pytest.raises(ValueError):
        create_agent("claude", "unknown", "job-1", "https://example.com", "prompt")


# --- run_agent (claude) ---


def test_run_agent_calls_instructor_and_returns_dict(mocker: MockerFixture) -> None:
    crawl_output = CrawlOutput(
        llms_txt="# Content",
        metadata=SiteMetadata(tech_stack=[], integrations=[], content_types=[]),
    )
    mock_completion = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=10, output_tokens=5)
    )
    mock_client = MagicMock()
    mock_client.messages.create_with_completion.return_value = (
        crawl_output,
        mock_completion,
    )
    mocker.patch("src.services.llm._get_instructor_client", return_value=mock_client)
    ctx = _make_claude_ctx()

    result = run_agent(ctx, "crawl this")

    assert result == crawl_output.model_dump()
    ctx["hooks"].on_start.assert_called_once()
    ctx["hooks"].on_complete.assert_called_once()


def test_run_agent_passes_extra_tools_when_present(mocker: MockerFixture) -> None:
    crawl_output = CrawlOutput(
        llms_txt="# Content",
        metadata=SiteMetadata(tech_stack=[], integrations=[], content_types=[]),
    )
    mock_completion = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=10, output_tokens=5)
    )
    mock_client = MagicMock()
    mock_create = mock_client.messages.create_with_completion
    mock_create.return_value = (crawl_output, mock_completion)
    mocker.patch("src.services.llm._get_instructor_client", return_value=mock_client)
    extra_tools = [{"type": "web_search_20250305", "name": "web_search"}]
    ctx = _make_claude_ctx(extra_tools=extra_tools)

    run_agent(ctx, "crawl this")

    _, kwargs = mock_create.call_args
    assert kwargs["tools"] == extra_tools


def test_run_agent_calls_on_error_and_reraises(mocker: MockerFixture) -> None:
    mock_client = MagicMock()
    mock_client.messages.create_with_completion.side_effect = RuntimeError("timeout")
    mocker.patch("src.services.llm._get_instructor_client", return_value=mock_client)
    ctx = _make_claude_ctx()
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


# --- openai ---


def test_create_agent_openai_crawl_returns_correct_context() -> None:
    ctx = create_agent("openai", "crawl", "job-1", "https://example.com", "prompt")
    assert ctx["provider"] == "openai"
    assert len(ctx["agent"].tools) == 2
    assert any(isinstance(t, WebSearchTool) for t in ctx["agent"].tools)


def test_create_agent_openai_report_has_no_web_tools() -> None:
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
