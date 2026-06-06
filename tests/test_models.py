import pytest
from pydantic import ValidationError

from src.constants import JobStatus, ModelName
from src.models import CrawlRequest


def test_job_status_serializes_to_string() -> None:
    assert JobStatus.COMPLETE == "complete"


def test_crawl_request_defaults_to_claude() -> None:
    request = CrawlRequest(url="https://example.com")
    assert request.model == ModelName.CLAUDE


def test_crawl_request_rejects_unknown_model() -> None:
    with pytest.raises(ValidationError):
        CrawlRequest(url="https://example.com", model="gpt-4")
