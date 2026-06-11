import pytest
from pytest_mock import MockerFixture

from src.agents.comparer import run_comparer
from src.constants import ArtifactType
from src.prompts import _build_compare_message


def test_comparer_runs_agent_with_both_contents(mocker: MockerFixture) -> None:
    job_a = {"url": "https://example.com", "model": "model-alpha"}
    job_b = {"url": "https://example.com", "model": "model-beta"}
    mocker.patch("src.agents.comparer.get_job", side_effect=[job_a, job_b])
    mocker.patch(
        "src.agents.comparer.get_artifact_content",
        side_effect=["# Content A", "# Content B"],
    )
    mocker.patch("src.agents.comparer.create_agent", return_value={})
    mock_run = mocker.patch("src.agents.comparer.run_agent", return_value={})

    run_comparer("job-compare-1", "job-a-1", "job-b-1", "claude")

    message = mock_run.call_args[0][1]
    assert "# Content A" in message
    assert "# Content B" in message
    assert "model-alpha" in message
    assert "model-beta" in message


def test_comparer_passes_correct_params_to_create_agent(mocker: MockerFixture) -> None:
    job_a = {"url": "https://example.com", "model": "claude"}
    job_b = {"url": "https://example.com", "model": "claude"}
    mocker.patch("src.agents.comparer.get_job", side_effect=[job_a, job_b])
    mocker.patch(
        "src.agents.comparer.get_artifact_content",
        side_effect=["# Content A", "# Content B"],
    )
    mock_create = mocker.patch("src.agents.comparer.create_agent", return_value={})
    mocker.patch("src.agents.comparer.run_agent", return_value={})

    run_comparer("job-compare-1", "job-a-1", "job-b-1", "claude")

    mock_create.assert_called_once_with(
        model="claude",
        agent_type="compare",
        job_id="job-compare-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )


def test_compare_message_labels_reports_by_model_name() -> None:
    job_a = {"url": "https://example.com", "model": "claude"}
    job_b = {"url": "https://example.com", "model": "openai"}

    message = _build_compare_message(job_a, "content a", job_b, "content b")

    assert "--- claude ---" in message
    assert "--- openai ---" in message
    assert "Model A" not in message
    assert "Model B" not in message


def test_comparer_notes_different_urls() -> None:
    job_a = {"url": "https://site-a.com", "model": "claude"}
    job_b = {"url": "https://site-b.com", "model": "claude"}

    message = _build_compare_message(job_a, "content a", job_b, "content b")

    assert "Note:" in message
    assert "https://site-a.com" in message
    assert "https://site-b.com" in message


def test_comparer_fails_if_content_unavailable(mocker: MockerFixture) -> None:
    job_a = {"url": "https://example.com", "model": "claude"}
    job_b = {"url": "https://example.com", "model": "claude"}
    mocker.patch("src.agents.comparer.get_job", side_effect=[job_a, job_b])
    mocker.patch(
        "src.agents.comparer.get_artifact_content",
        side_effect=["# Content A", None],
    )
    mock_fail = mocker.patch("src.agents.comparer.fail_artifact")
    mock_run = mocker.patch("src.agents.comparer.run_agent")

    run_comparer("job-compare-1", "job-a-1", "job-b-1", "claude")

    mock_fail.assert_called_once()
    mock_run.assert_not_called()


def test_comparer_fails_artifact_on_unexpected_error(mocker: MockerFixture) -> None:
    mocker.patch("src.agents.comparer.get_job", side_effect=RuntimeError("db error"))
    mock_fail = mocker.patch("src.agents.comparer.fail_artifact")

    with pytest.raises(RuntimeError, match="db error"):
        run_comparer("job-compare-1", "job-a-1", "job-b-1", "claude")

    mock_fail.assert_called_once_with("job-compare-1", ArtifactType.COMPARISON, "db error")
