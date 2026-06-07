from pytest_mock import MockerFixture

from src.services.search import run_search

_PINECONE_MATCHES = [
    {
        "id": "job-1",
        "score": 0.95,
        "metadata": {
            "url": "https://example.com",
            "s3Key": "results/job-1/llms.txt",
            "model": "claude",
        },
    },
    {
        "id": "job-2",
        "score": 0.80,
        "metadata": {
            "url": "https://other.com",
            "s3Key": "results/job-2/llms.txt",
            "model": "claude",
        },
    },
]


def test_search_returns_ranked_results(mocker: MockerFixture) -> None:
    mocker.patch("src.services.search.embed_text", return_value=[0.1, 0.2, 0.3])
    mocker.patch("src.services.search.query_vectors", return_value=_PINECONE_MATCHES)
    mocker.patch(
        "src.services.search.generate_download_url",
        side_effect=lambda s3_key: f"https://s3.presigned/{s3_key}",
    )

    response = run_search("find documentation tools")

    assert response.query == "find documentation tools"
    assert response.error is None
    assert len(response.results) == 2

    first, second = response.results
    assert first.jobId == "job-1"
    assert first.score == 0.95
    assert first.url == "https://example.com"
    assert first.downloadUrl == "https://s3.presigned/results/job-1/llms.txt"
    assert second.jobId == "job-2"
    assert second.score == 0.80


def test_search_empty_query_returns_empty(mocker: MockerFixture) -> None:
    mock_query = mocker.patch("src.services.search.query_vectors")

    response = run_search("")

    assert response.query == ""
    assert response.results == []
    assert response.error is None
    mock_query.assert_not_called()


def test_search_pinecone_error_returns_error_field(mocker: MockerFixture) -> None:
    mocker.patch("src.services.search.embed_text", side_effect=Exception("timeout"))

    response = run_search("some query")

    assert response.results == []
    assert response.error == "Search unavailable"
