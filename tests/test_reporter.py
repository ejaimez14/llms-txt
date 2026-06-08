from pytest_mock import MockerFixture

from src.agents.reporter import run_reporter


def test_reporter_runs_agent_with_llms_txt_content(mocker: MockerFixture) -> None:
    site = {"latestJobId": "job-crawl-1"}
    mocker.patch("src.agents.reporter.get_site", return_value=site)
    mocker.patch(
        "src.agents.reporter.get_artifact_content", return_value="# Example llms.txt"
    )
    mocker.patch("src.agents.reporter.create_agent", return_value={})
    mock_run = mocker.patch("src.agents.reporter.run_agent", return_value={})

    run_reporter("job-report-1", "https://example.com", "claude")

    call_args = mock_run.call_args
    assert "# Example llms.txt" in call_args[0][1]


def test_reporter_passes_correct_params_to_create_agent(mocker: MockerFixture) -> None:
    site = {"latestJobId": "job-crawl-1"}
    mocker.patch("src.agents.reporter.get_site", return_value=site)
    mocker.patch("src.agents.reporter.get_artifact_content", return_value="# Content")
    mock_create = mocker.patch("src.agents.reporter.create_agent", return_value={})
    mocker.patch("src.agents.reporter.run_agent", return_value={})

    run_reporter("job-report-1", "https://example.com", "claude")

    mock_create.assert_called_once_with(
        model="claude",
        agent_type="report",
        job_id="job-report-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
    )


def test_reporter_fails_if_site_not_crawled(mocker: MockerFixture) -> None:
    mocker.patch("src.agents.reporter.get_site", return_value=None)
    mock_fail = mocker.patch("src.agents.reporter.fail_artifact")
    mock_run = mocker.patch("src.agents.reporter.run_agent")

    run_reporter("job-report-1", "https://example.com", "claude")

    mock_fail.assert_called_once()
    assert "https://example.com" in mock_fail.call_args[0][2]
    mock_run.assert_not_called()


def test_reporter_fails_if_content_unavailable(mocker: MockerFixture) -> None:
    site = {"latestJobId": "job-crawl-1"}
    mocker.patch("src.agents.reporter.get_site", return_value=site)
    mocker.patch("src.agents.reporter.get_artifact_content", return_value=None)
    mock_fail = mocker.patch("src.agents.reporter.fail_artifact")
    mock_run = mocker.patch("src.agents.reporter.run_agent")

    run_reporter("job-report-1", "https://example.com", "claude")

    mock_fail.assert_called_once()
    mock_run.assert_not_called()
