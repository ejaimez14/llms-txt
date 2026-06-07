from unittest.mock import MagicMock, patch

from src.services.tools import web_fetch


def test_web_fetch_returns_plain_text_from_html() -> None:
    mock_response = MagicMock()
    mock_response.text = "<html><body><h1>Hello</h1><p>World</p></body></html>"

    with patch("src.services.tools.httpx.get", return_value=mock_response):
        result = web_fetch("https://example.com")

    assert "Hello" in result
    assert isinstance(result, str)


def test_web_fetch_returns_error_string_on_failure() -> None:
    with patch("src.services.tools.httpx.get", side_effect=ConnectionError("refused")):
        result = web_fetch("https://example.com")

    assert result.startswith("Failed to fetch https://example.com")
