from __future__ import annotations

import logging

from etl.analytics.context.request_context import get_request_context


class RequestContextFilter(logging.Filter):
    """Attach request-scoped identity fields to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_request_context()

        record.request_id = (
            str(context.request_id) if context is not None else None
        )
        record.user_id = (
            str(context.user_id)
            if context is not None and context.user_id is not None
            else None
        )
        record.tenant_id = (
            str(context.tenant_id)
            if context is not None and context.tenant_id is not None
            else None
        )

        return True


class ObservabilityFormatter(logging.Formatter):
    """Format application logs with request context."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)

        return (
            f"{message} "
            f"request_id={getattr(record, 'request_id', None)} "
            f"user_id={getattr(record, 'user_id', None)} "
            f"tenant_id={getattr(record, 'tenant_id', None)}"
        )


def configure_logging() -> None:
    """Configure application logging."""

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        ObservabilityFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)