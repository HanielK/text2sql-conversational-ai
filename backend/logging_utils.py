import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "event_data") and isinstance(record.event_data, dict):
            payload.update(record.event_data)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logger(name: str = "text2sql") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if settings.ENABLE_FILE_LOGGING:
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join(settings.LOG_DIR, "app.log"),
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()


def new_request_id() -> str:
    return str(uuid.uuid4())


def log_event(
    logger_obj: logging.Logger,
    message: str,
    request_id: str,
    stage: str,
    status: str = "ok",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    event_data = {
        "request_id": request_id,
        "stage": stage,
        "status": status,
    }
    if extra:
        event_data.update(extra)

    logger_obj.info(message, extra={"event_data": event_data})