"""CloudWatch-friendly structured logging utilities."""

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Render log records as JSON for CloudWatch parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_structured_logging(app):
    """Configure root/app loggers with JSON format once."""
    if app.logger.handlers:
        app.logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
