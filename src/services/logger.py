import json
import logging
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Formats each log record as a single JSON object for CloudWatch structured queries."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
        }
        if isinstance(record.msg, dict):
            payload.update(record.msg)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """Returns a configured Python logger that emits one JSON object per line."""
    logger = logging.getLogger(name)

    # Avoid duplicate handlers when the same logger is retrieved more than once
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    logger.setLevel(logging.INFO)
    return logger


def log_job_event(
    logger: logging.Logger,
    event: str,
    job_id: str,
    **kwargs: Any,
) -> None:
    """Logs a structured event with consistent fields; extra kwargs are merged into the JSON output."""
    logger.info({"event": event, "jobId": job_id, **kwargs})
