"""
Structured JSON logging using structlog and standard library logging integration.
Ensures uniform log output with correlation IDs, timestamps, and log levels.
"""
import logging
import sys
import structlog
from app.core.config import settings


SENSITIVE_KEYS = {
    "password",
    "raw_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "authorization",
    "api_key",
    "openai_api_key",
    "card_number",
    "cvv",
    "cookie",
}


def mask_sensitive_data(logger_inst, method_name, event_dict):
    """
    Sanitizes log context dictionaries to prevent accidental leakage
    of credentials, tokens, or financial identifiers in operational telemetry.
    """
    for key in list(event_dict.keys()):
        lower_key = str(key).lower()
        if any(s in lower_key for s in SENSITIVE_KEYS):
            val = event_dict[key]
            if isinstance(val, str) and len(val) > 8:
                event_dict[key] = f"{val[:3]}...[REDACTED]...{val[-3:]}"
            else:
                event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        mask_sensitive_data,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.DEBUG or settings.ENVIRONMENT == "development":
        # Human-friendly colored output in development
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Machine-parseable JSON in staging and production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Silence overly verbose third-party loggers
    for logger_name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).propagate = True


def get_logger(name: str = __name__):
    """Retrieve a structured logger instance."""
    return structlog.get_logger(name)
