from pytest_mock import MockerFixture

from src.agents import crawler
from src.agents.crawler import run_crawler


def test_run_crawler_passes_correct_params(mocker: MockerFixture) -> None:
    mock_create = mocker.patch("src.agents.crawler.create_agent", return_value={})
    mocker.patch("src.agents.crawler.run_agent", return_value={})

    run_crawler("job-1", "https://example.com", "claude")

    mock_create.assert_called_once_with(
        model="claude",
        agent_type="crawl",
        job_id="job-1",
        url="https://example.com",
        system_prompt=mocker.ANY,
        tools=mocker.ANY,
        submit_tool_name="submit_crawl_results",
    )


def test_run_crawler_returns_run_agent_output(mocker: MockerFixture) -> None:
    expected = {"llms_txt": "# Example", "metadata": {}}
    mocker.patch("src.agents.crawler.create_agent", return_value={})
    mocker.patch("src.agents.crawler.run_agent", return_value=expected)

    result = run_crawler("job-2", "https://example.com", "claude")

    assert result == expected


def test_crawler_no_direct_storage_calls() -> None:
    assert not hasattr(crawler, "save_llms_txt")
    assert not hasattr(crawler, "embed_text")
    assert not hasattr(crawler, "upsert_vector")
