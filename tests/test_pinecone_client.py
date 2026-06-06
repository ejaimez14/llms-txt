import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _pinecone_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PINECONE_API_KEY", "test-api-key")
    monkeypatch.setenv("PINECONE_INDEX", "test-index")


@pytest.fixture()
def mock_index() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def pinecone_module(mock_index: MagicMock) -> object:
    """Imports pinecone_client with Pinecone fully mocked, re-imported fresh per test."""
    mock_pinecone_pkg = MagicMock()
    mock_pinecone_pkg.Pinecone.return_value.Index.return_value = mock_index
    sys.modules["pinecone"] = mock_pinecone_pkg
    sys.modules.pop("src.services.pinecone_client", None)

    import src.services.pinecone_client as module

    yield module

    sys.modules.pop("src.services.pinecone_client", None)
    sys.modules.pop("pinecone", None)


# --- Tests ---


def test_upsert_vector_calls_index(pinecone_module: object, mock_index: MagicMock) -> None:
    vector = [0.1, 0.2, 0.3]
    metadata = {"url": "https://example.com", "s3Key": "results/abc123/llms.txt", "model": "claude"}

    pinecone_module.upsert_vector("job-abc123", vector, metadata)

    mock_index.upsert.assert_called_once_with(
        vectors=[{"id": "job-abc123", "values": vector, "metadata": metadata}]
    )


def test_query_vectors_returns_ranked_results(pinecone_module: object, mock_index: MagicMock) -> None:
    mock_index.query.return_value = {
        "matches": [
            {"id": "job-1", "score": 0.95, "metadata": {"url": "https://example.com", "s3Key": "k1"}},
            {"id": "job-2", "score": 0.80, "metadata": {"url": "https://other.com", "s3Key": "k2"}},
        ]
    }

    results = pinecone_module.query_vectors([0.1, 0.2, 0.3], top_k=2)

    assert len(results) == 2
    assert results[0]["id"] == "job-1"
    assert results[0]["score"] == 0.95


def test_query_vectors_error_raises(pinecone_module: object, mock_index: MagicMock) -> None:
    mock_index.query.side_effect = Exception("connection refused")

    with pytest.raises(Exception, match="connection refused"):
        pinecone_module.query_vectors([0.1, 0.2, 0.3])
