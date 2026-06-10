from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

import src.services.pinecone_client as pinecone_module


@pytest.fixture()
def mock_index(mocker: MockerFixture) -> MagicMock:
    index = MagicMock()
    mocker.patch.object(pinecone_module, "_index", index)
    return index


# --- Tests ---


def test_upsert_vector_calls_index(mock_index: MagicMock) -> None:
    vector = [0.1, 0.2, 0.3]
    metadata = {
        "url": "https://example.com",
        "s3Key": "results/abc123/llms.txt",
        "model": "claude",
    }

    pinecone_module.upsert_vector("job-abc123", vector, metadata)

    mock_index.upsert.assert_called_once_with(
        vectors=[{"id": "job-abc123", "values": vector, "metadata": metadata}]
    )


def test_upsert_vector_drops_null_metadata(mock_index: MagicMock) -> None:
    vector = [0.1, 0.2, 0.3]
    metadata = {"url": "https://example.com", "business_model": None, "tone": None}

    pinecone_module.upsert_vector("job-1", vector, metadata)

    mock_index.upsert.assert_called_once_with(
        vectors=[
            {
                "id": "job-1",
                "values": vector,
                "metadata": {"url": "https://example.com"},
            }
        ]
    )


def test_query_vectors_returns_ranked_results(mock_index: MagicMock) -> None:
    mock_index.query.return_value = {
        "matches": [
            {
                "id": "job-1",
                "score": 0.95,
                "metadata": {"url": "https://example.com", "s3Key": "k1"},
            },
            {
                "id": "job-2",
                "score": 0.80,
                "metadata": {"url": "https://other.com", "s3Key": "k2"},
            },
        ]
    }

    results = pinecone_module.query_vectors([0.1, 0.2, 0.3], top_k=2)

    assert len(results) == 2
    assert results[0]["id"] == "job-1"
    assert results[0]["score"] == 0.95


def test_query_vectors_error_raises(mock_index: MagicMock) -> None:
    mock_index.query.side_effect = Exception("connection refused")

    with pytest.raises(Exception, match="connection refused"):
        pinecone_module.query_vectors([0.1, 0.2, 0.3])
