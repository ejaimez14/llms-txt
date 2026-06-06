import sys
from unittest.mock import MagicMock

import pytest


# Patch Pinecone at import time so module-level client instantiation doesn't
# require real credentials. The module is re-imported fresh for each test via
# the fixture below.
@pytest.fixture(autouse=True)
def _pinecone_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PINECONE_API_KEY", "test-api-key")
    monkeypatch.setenv("PINECONE_INDEX", "test-index")


@pytest.fixture()
def mock_index() -> MagicMock:
    """Returns a mock Pinecone Index and patches the module-level _index."""
    index = MagicMock()
    return index


@pytest.fixture()
def pinecone_module(mock_index: MagicMock) -> object:
    """Imports pinecone_client with Pinecone fully mocked, returning the module."""
    mock_pinecone_instance = MagicMock()
    mock_pinecone_instance.Index.return_value = mock_index

    # Stub the entire pinecone package so the import doesn't hit the real SDK.
    mock_pinecone_pkg = MagicMock()
    mock_pinecone_pkg.Pinecone = MagicMock(return_value=mock_pinecone_instance)
    sys.modules["pinecone"] = mock_pinecone_pkg

    # Remove cached module so the patched Pinecone is used on import.
    sys.modules.pop("src.services.pinecone_client", None)
    import src.services.pinecone_client as module

    yield module

    # Clean up so the patched version doesn't bleed into other tests.
    sys.modules.pop("src.services.pinecone_client", None)
    sys.modules.pop("pinecone", None)


# --- Tests ---


def test_upsert_vector_succeeds(
    pinecone_module: object, mock_index: MagicMock
) -> None:
    job_id = "job-abc123"
    vector = [0.1, 0.2, 0.3]
    metadata = {
        "url": "https://example.com",
        "s3Key": "results/abc123/llms.txt",
        "model": "claude",
    }

    pinecone_module.upsert_vector(job_id, vector, metadata)

    mock_index.upsert.assert_called_once_with(
        vectors=[{"id": job_id, "values": vector, "metadata": metadata}]
    )
    upserted = mock_index.upsert.call_args[1]["vectors"][0]
    assert "url" in upserted["metadata"]
    assert "s3Key" in upserted["metadata"]


def test_query_vectors_returns_ranked_results(
    pinecone_module: object, mock_index: MagicMock
) -> None:
    vector = [0.1, 0.2, 0.3]
    mock_index.query.return_value = {
        "matches": [
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
    }

    results = pinecone_module.query_vectors(vector, top_k=2)

    mock_index.query.assert_called_once_with(
        vector=vector, top_k=2, include_metadata=True
    )
    assert len(results) == 2
    first = results[0]
    assert first["id"] == "job-1"
    assert first["score"] == 0.95
    assert "url" in first["metadata"]
    assert "s3Key" in first["metadata"]


def test_query_vectors_connection_error_raises(
    pinecone_module: object, mock_index: MagicMock
) -> None:
    vector = [0.1, 0.2, 0.3]
    mock_index.query.side_effect = Exception("connection refused")

    with pytest.raises(Exception, match="connection refused"):
        pinecone_module.query_vectors(vector)
