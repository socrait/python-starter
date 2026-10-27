import io
import json
import logging
from typing import Any

import pytest
import structlog

from starter_app.libs.structured_logging import LogConfig, configure_logging, get_logger


@pytest.fixture
def log_output() -> io.StringIO:
    configure_logging(
        LogConfig(app_name="test-app", environment="test", format="json", level_key="severity")
    )
    buffer = io.StringIO()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    handler.setStream(buffer)
    return buffer


def _last_event(buffer: io.StringIO) -> dict[str, Any]:
    return json.loads(buffer.getvalue().strip().splitlines()[-1])


def test_structlog_events_render_as_json_with_context(log_output: io.StringIO):
    structlog.contextvars.bind_contextvars(request_id="req-1")
    try:
        get_logger("test").info("thing_happened", thing_id="t1")
    finally:
        structlog.contextvars.clear_contextvars()

    event = _last_event(log_output)
    assert event["event"] == "thing_happened"
    assert event["thing_id"] == "t1"
    assert event["request_id"] == "req-1"
    assert event["severity"] == "INFO"
    assert event["app"] == "test-app"


def test_stdlib_loggers_share_the_format(log_output: io.StringIO):
    logging.getLogger("some.library").warning("library said %s", "hi")

    event = _last_event(log_output)
    assert event["event"] == "library said hi"
    assert event["logger"] == "some.library"


def test_exceptions_render_without_local_variables(log_output: io.StringIO):
    secret = "hunter2"
    try:
        raise ValueError("bad")
    except ValueError:
        get_logger("test").exception("it_failed")

    event = _last_event(log_output)
    assert event["exception"][0]["exc_type"] == "ValueError"
    assert secret not in log_output.getvalue()
