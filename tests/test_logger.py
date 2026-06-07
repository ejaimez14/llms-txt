import json
import logging

from src.services.logger import _JsonFormatter, get_logger


def _make_record(msg: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    return record


def test_dict_message_fields_appear_in_json() -> None:
    """Dict messages are flattened into the JSON output alongside timestamp and level."""
    formatter = _JsonFormatter()
    record = _make_record({"event": "crawl_started", "jobId": "abc123"})

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "crawl_started"
    assert payload["jobId"] == "abc123"
    assert "timestamp" in payload
    assert payload["level"] == "INFO"


def test_non_dict_message_does_not_crash() -> None:
    """Plain string messages are handled without error — only timestamp and level emitted."""
    formatter = _JsonFormatter()
    record = _make_record("plain string")

    payload = json.loads(formatter.format(record))

    assert "timestamp" in payload
    assert payload["level"] == "INFO"


def test_get_logger_does_not_add_duplicate_handlers() -> None:
    """Calling get_logger twice with the same name does not add a second handler."""
    logger = logging.getLogger("test_dedup")
    logger.handlers.clear()

    get_logger("test_dedup")
    get_logger("test_dedup")

    assert len(logger.handlers) == 1
