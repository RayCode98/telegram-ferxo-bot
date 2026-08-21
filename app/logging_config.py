from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

_STANDARD = {"name","msg","args","levelname","levelno","pathname","filename","module","exc_info","exc_text","stack_info","lineno","funcName","created","msecs","relativeCreated","thread","threadName","processName","process","taskName"}

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD and not key.startswith("_"):
                try:
                    json.dumps(value); payload[key] = value
                except TypeError:
                    payload[key] = str(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

def configure_logging() -> None:
    root = logging.getLogger(); root.handlers.clear()
    handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root.addHandler(handler); root.setLevel(logging.INFO)
