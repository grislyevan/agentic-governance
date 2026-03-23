"""Structured logging configuration for the Detec API."""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar

from pythonjsonlogger import json

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class DetecJsonFormatter(json.JsonFormatter):
    def add_fields(self, log_data: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_data, record, message_dict)
        log_data["timestamp"] = record.created
        log_data["level"] = record.levelname
        log_data["logger"] = record.name
        if getattr(record, "request_id", None):
            log_data["request_id"] = record.request_id


def configure_logging() -> None:
    """Configure logging based on ENV. Call at app startup."""
    env = os.getenv("ENV", "development").lower()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if env == "development" else logging.INFO)

    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    if env == "production":
        handler.setFormatter(DetecJsonFormatter())
        handler.addFilter(RequestIdFilter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        try:
            import colorlog
            handler.setFormatter(
                colorlog.ColoredFormatter(
                    "%(log_color)s%(asctime)s %(levelname)s [%(name)s] %(message)s%(reset)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        except ImportError:
            pass

    root.addHandler(handler)
