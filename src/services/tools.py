import html2text as _html2text
import httpx
from agents import function_tool


def web_fetch(url: str) -> str:
    """Fetch the content of a URL and return it as plain text markdown."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        return _html2text.html2text(response.text)
    except Exception as exc:
        return f"Failed to fetch {url}: {exc}"


web_fetch_tool = function_tool(web_fetch)
