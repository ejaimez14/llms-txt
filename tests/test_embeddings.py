import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import src.services.embeddings as embeddings_module
from src.services.embeddings import embed_text


def _make_bedrock_response(vector: list[float]) -> dict:
    """Build a minimal bedrock-runtime invoke_model response with the given embedding."""
    body_bytes = json.dumps({"embedding": vector}).encode()
    return {"body": BytesIO(body_bytes)}


def test_embed_text_returns_float_list(mocker: MagicMock) -> None:
    """embed_text returns a non-empty list[float] for valid input."""
    expected_vector = [0.1, 0.2, 0.3]
    mock_client = mocker.patch.object(
        embeddings_module, "_bedrock_client", autospec=True
    )
    mock_client.invoke_model.return_value = _make_bedrock_response(expected_vector)

    result = embed_text("hello world")

    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(v, float) for v in result)
    assert result == expected_vector


def test_embed_calls_bedrock_titan(mocker: MagicMock) -> None:
    """embed_text invokes bedrock-runtime with model amazon.titan-embed-text-v1."""
    mock_client = mocker.patch.object(
        embeddings_module, "_bedrock_client", autospec=True
    )
    mock_client.invoke_model.return_value = _make_bedrock_response([0.5])

    embed_text("some text")

    mock_client.invoke_model.assert_called_once()
    call_kwargs = mock_client.invoke_model.call_args.kwargs
    assert call_kwargs["modelId"] == "amazon.titan-embed-text-v1"
    assert call_kwargs["contentType"] == "application/json"
    assert call_kwargs["accept"] == "application/json"
    sent_body = json.loads(call_kwargs["body"])
    assert sent_body["inputText"] == "some text"


def test_embed_truncates_long_input(mocker: MagicMock) -> None:
    """Input longer than 8000 characters is truncated before the API call."""
    mock_client = mocker.patch.object(
        embeddings_module, "_bedrock_client", autospec=True
    )
    mock_client.invoke_model.return_value = _make_bedrock_response([0.9])

    long_input = "x" * 9000
    embed_text(long_input)

    call_kwargs = mock_client.invoke_model.call_args.kwargs
    sent_body = json.loads(call_kwargs["body"])
    assert len(sent_body["inputText"]) == 8000


def test_embed_returns_empty_list_for_empty_string() -> None:
    """embed_text returns [] for an empty string without calling Bedrock."""
    result = embed_text("")
    assert result == []


def test_embed_returns_empty_list_for_none() -> None:
    """embed_text returns [] for None without calling Bedrock."""
    result = embed_text(None)
    assert result == []


def test_embed_bedrock_error_raises(mocker: MagicMock) -> None:
    """embed_text logs and re-raises ClientError when the Bedrock call fails."""
    mock_client = mocker.patch.object(
        embeddings_module, "_bedrock_client", autospec=True
    )
    client_error = ClientError(
        {"Error": {"Code": "ServiceUnavailableException", "Message": "Bedrock unavailable"}},
        "InvokeModel",
    )
    mock_client.invoke_model.side_effect = client_error

    mock_logger = mocker.patch.object(embeddings_module, "logger")

    with pytest.raises(ClientError):
        embed_text("some text")

    mock_logger.info.assert_called_once_with(
        {"event": "bedrock_embed_failed", "error": str(client_error)}
    )
