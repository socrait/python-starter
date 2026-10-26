import logging

import structlog

from starter_app.config import Settings
from starter_app.libs.structured_logging import LogConfig, configure_logging
from starter_app.libs.structured_logging import get_logger as _get_logger


def configure_logging_from_settings(settings: Settings) -> None:
    vendor_levels = {"sqlalchemy.engine": logging.INFO} if settings.log_sql else {}
    configure_logging(
        LogConfig(
            app_name=settings.app_name,
            environment=settings.environment.value,
            level=settings.log_level.to_logging_level(),
            vendor_level=settings.log_level_vendor.to_logging_level(),
            format="json" if settings.log_format == "json" else "text",
            level_key=settings.log_level_key,
            vendor_levels=vendor_levels,
        )
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return _get_logger(name)
