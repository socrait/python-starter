from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from sqlalchemy import Engine

from starter_app.config import Environment, Settings
from starter_app.core.models import Actor
from starter_app.libs.metrics import make_meter_provider
from starter_app.main import make_app
from starter_app.metrics import make_metrics_config
from tests.fixtures.metrics import histogram_points

type HeadersFor = Callable[[Actor], dict[str, str]]


def test_health_and_ready(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ok"}


def test_requests_are_measured_by_route_template(
    settings: Settings, engine: Engine, metrics_reader: InMemoryMetricReader
):
    provider = make_meter_provider(make_metrics_config(settings), readers=(metrics_reader,))
    app = make_app(settings, engine=engine, meter_provider=provider)

    with TestClient(app) as client:
        client.get("/projects/prj_123")
        client.get("/health")

    points = histogram_points(metrics_reader, "http.server.request.duration")
    routes = [(p.attributes or {}).get("http.route") for p in points]
    assert routes == ["/projects/{project_id}"]  # probes are excluded


def test_request_id_is_echoed_and_generated(client: TestClient):
    echoed = client.get("/health", headers={"X-Request-ID": "0" * 32})
    generated = client.get("/health")

    assert echoed.headers["X-Request-ID"] == "0" * 32
    assert len(generated.headers["X-Request-ID"]) == 32


def test_responses_are_not_cacheable(client: TestClient):
    assert client.get("/health").headers["cache-control"] == "no-store"


def test_validation_errors_share_the_error_shape(
    client: TestClient, auth_headers: HeadersFor, sample_member: Actor
):
    response = client.post("/projects", headers=auth_headers(sample_member), json={"name": ""})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert body["details"][0]["loc"] == ["body", "name"]
    assert body["requestId"]


def test_unknown_route_uses_the_error_shape(client: TestClient):
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unexpected_errors_reveal_nothing(settings: Settings, engine: Engine):
    app = make_app(settings, engine=engine)  # own app: the route below must not leak into others

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("secret internals")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "secret" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["requestId"]


def test_deployed_app_refuses_dev_auth():
    with pytest.raises(RuntimeError, match="No Authenticator configured"):
        make_app(
            Settings(
                _env_file=None,
                environment=Environment.PRODUCTION,
                dev_auth_enabled=False,
            )
        )
