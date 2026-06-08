from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

import src.agents.implementer as implementer_module
from src.agents.implementer import _run_agent, run_implementer
from src.constants import ArtifactType


def _make_async_query(exc: Exception | None = None):
    """Returns an async generator factory that either yields nothing or raises exc."""

    async def _gen(*args, **kwargs):
        if exc is not None:
            raise exc
        return
        yield  # make it an async generator

    return _gen


@pytest.fixture
def mock_get_artifact_content(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(
        implementer_module, "get_artifact_content", return_value="## UI Plan\n..."
    )


@pytest.fixture
def mock_fail_artifact(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(implementer_module, "fail_artifact")


@pytest.fixture
def mock_complete_artifact(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(implementer_module, "complete_artifact")


def test_run_implementer_fails_if_plan_unavailable(
    mocker: MockerFixture,
    mock_fail_artifact: MagicMock,
) -> None:
    mocker.patch.object(implementer_module, "get_artifact_content", return_value=None)
    mock_run_agent = mocker.patch.object(implementer_module, "_run_agent")

    run_implementer("job-1", "source-1", "owner/repo", "main")

    mock_fail_artifact.assert_called_once_with(
        "job-1", ArtifactType.PR_URL, "UI plan content unavailable"
    )
    mock_run_agent.assert_not_called()


def test_run_implementer_runs_agent_with_plan_content(
    mocker: MockerFixture,
    mock_get_artifact_content: MagicMock,
    mock_fail_artifact: MagicMock,
) -> None:
    mock_run_agent = AsyncMock()
    mocker.patch.object(implementer_module, "_run_agent", mock_run_agent)

    run_implementer("job-2", "source-2", "owner/repo", "main")

    mock_run_agent.assert_called_once_with(
        "job-2", "## UI Plan\n...", "owner/repo", "main"
    )
    mock_fail_artifact.assert_not_called()


def test_run_implementer_fails_on_agent_exception(
    mocker: MockerFixture,
    mock_get_artifact_content: MagicMock,
    mock_fail_artifact: MagicMock,
) -> None:
    async def _raise(*args, **kwargs):
        raise RuntimeError("SDK boom")

    mocker.patch.object(implementer_module, "_run_agent", side_effect=_raise)

    run_implementer("job-3", "source-3", "owner/repo", "main")

    mock_fail_artifact.assert_called_once_with("job-3", ArtifactType.PR_URL, "SDK boom")


@pytest.mark.asyncio
async def test_run_implementer_reads_pr_url_and_completes_artifact(
    tmp_path: Path,
    mocker: MockerFixture,
    mock_complete_artifact: MagicMock,
    mock_fail_artifact: MagicMock,
) -> None:
    mocker.patch.object(implementer_module, "query", side_effect=_make_async_query())
    mocker.patch(
        "tempfile.TemporaryDirectory",
        return_value=MagicMock(
            __enter__=lambda s: str(tmp_path),
            __exit__=MagicMock(return_value=False),
        ),
    )
    (tmp_path / "pr-url.txt").write_text("https://github.com/owner/repo/pull/42")

    await _run_agent("job-4", "## Plan", "owner/repo", "main")

    mock_complete_artifact.assert_called_once_with(
        "job-4", ArtifactType.PR_URL, "https://github.com/owner/repo/pull/42"
    )
    mock_fail_artifact.assert_not_called()


@pytest.mark.asyncio
async def test_run_implementer_fails_if_pr_url_missing(
    tmp_path: Path,
    mocker: MockerFixture,
    mock_complete_artifact: MagicMock,
) -> None:
    mocker.patch.object(implementer_module, "query", side_effect=_make_async_query())
    mocker.patch(
        "tempfile.TemporaryDirectory",
        return_value=MagicMock(
            __enter__=lambda s: str(tmp_path),
            __exit__=MagicMock(return_value=False),
        ),
    )
    # pr-url.txt NOT created — agent forgot to write it

    with pytest.raises(FileNotFoundError, match="pr-url.txt"):
        await _run_agent("job-5", "## Plan", "owner/repo", "main")

    mock_complete_artifact.assert_not_called()
