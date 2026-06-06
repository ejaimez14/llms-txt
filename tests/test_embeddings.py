import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture

import src.services.embeddings as embeddings_module
from src.services.embeddings import embed_text


def _make_bedrock_response(vector: list[float]) -> dict:
    return {"body": BytesIO(json.dumps({"embedding": vector}).encode())}


@pytest.fixture()
def mock_bedrock(mocker: MockerFixture) -> MagicMock:
    return mocker.patch.object(embeddings_module, "_bedrock_client", autospec=True)


def test_embed_text_returns_vector(mock_bedrock: MagicMock) -> None:
    mock_bedrock.invoke_model.return_value = _make_bedrock_response([0.1, 0.2, 0.3])
    assert embed_text("hello world") == [0.1, 0.2, 0.3]


def test_embed_calls_titan_model(mock_bedrock: MagicMock) -> None:
    mock_bedrock.invoke_model.return_value = _make_bedrock_response([0.5])
    embed_text("some text")

    call_kwargs = mock_bedrock.invoke_model.call_args.kwargs
    assert call_kwargs["modelId"] == "amazon.titan-embed-text-v1"
    assert json.loads(call_kwargs["body"])["inputText"] == "some text"


def test_embed_truncates_long_input(mock_bedrock: MagicMock) -> None:
    mock_bedrock.invoke_model.return_value = _make_bedrock_response([0.9])
    embed_text("x" * 30000)

    sent_body = json.loads(mock_bedrock.invoke_model.call_args.kwargs["body"])
    assert len(sent_body["inputText"]) == 25000


def test_embed_returns_empty_for_empty_string() -> None:
    assert embed_text("") == []


def test_embed_returns_empty_for_none() -> None:
    assert embed_text(None) == []


def test_embed_bedrock_error_raises(mock_bedrock: MagicMock) -> None:
    mock_bedrock.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ServiceUnavailableException", "Message": "unavailable"}},
        "InvokeModel",
    )
    with pytest.raises(ClientError):
        embed_text("some text")
