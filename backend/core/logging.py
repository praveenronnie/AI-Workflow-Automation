"""Application-wide logging configuration."""

import contextvars
import logging
import sys
import uuid

# Set by the RequestID middleware; consumed by the log filter so every log
# line emitted while handling a request carries the same correlation id.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with filename/funcName + request id output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] "
            "[%(filename)s:%(funcName)s] %(message)s"
        )
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for the given module name."""
    return logging.getLogger(name)