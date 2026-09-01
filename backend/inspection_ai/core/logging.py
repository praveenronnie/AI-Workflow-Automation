"""Application-wide logging configuration."""

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(filename)s:%(funcName)s] %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with filename/funcName-formatted output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for the given module name."""
    return logging.getLogger(name)