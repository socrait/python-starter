from typing import Any

import pytest
from pydantic import ValidationError

from starter_app.config import Environment, LogFormat, Settings


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_local_defaults_favor_development():
    settings = _settings(environment=Environment.LOCAL)

    assert settings.log_format == LogFormat.TEXT
    assert settings.dev_auth_enabled is True
    assert settings.docs_enabled is True


def test_deployed_defaults_favor_safety():
    settings = _settings(environment=Environment.PRODUCTION)

    assert settings.log_format == LogFormat.JSON
    assert settings.dev_auth_enabled is False
    assert settings.docs_enabled is False


def test_dev_auth_cannot_be_forced_on_when_deployed():
    with pytest.raises(ValidationError, match="dev_auth_enabled"):
        _settings(environment=Environment.STAGING, dev_auth_enabled=True)
