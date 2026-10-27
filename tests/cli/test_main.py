import socket
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from starter_app.cli import main
from starter_app.config import get_settings


@pytest.fixture
def file_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    path = tmp_path / "cli.db"
    monkeypatch.setenv("STARTER_APP_DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("STARTER_APP_ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


@pytest.mark.usefixtures("file_database")
def test_create_seed_and_check(capsys: pytest.CaptureFixture[str]):
    assert main(["db", "create"]) == 0
    assert main(["db", "check"]) == 0
    assert main(["seed"]) == 0

    assert "X-User-Id: usr_" in capsys.readouterr().out


@pytest.mark.usefixtures("file_database")
def test_migrate_then_reset(capsys: pytest.CaptureFixture[str]):
    assert main(["db", "migrate"]) == 0
    assert main(["db", "reset", "--yes"]) == 0

    assert "Database reset." in capsys.readouterr().out


def test_reset_refuses_deployed_databases(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STARTER_APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        assert main(["db", "reset", "--yes"]) == 1
    finally:
        get_settings.cache_clear()


@pytest.mark.skipif(sys.version_info < (3, 15), reason="profiling.sampling is new in 3.15")
@pytest.mark.skipif(sys.platform == "darwin", reason="macOS profiling needs root")
def test_profile_writes_a_flame_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    monkeypatch.setenv("STARTER_APP_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("STARTER_APP_ENVIRONMENT", "test")
    monkeypatch.setenv("STARTER_APP_PORT", str(free_port))
    output = tmp_path / "profile.html"

    assert main(["profile", "--duration", "2", "-o", str(output)]) == 0
    assert output.stat().st_size > 0
