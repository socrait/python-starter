from collections.abc import Callable

from fastapi.testclient import TestClient

from starter_app.core.models import Actor

type HeadersFor = Callable[[Actor], dict[str, str]]


def test_me_returns_profile(client: TestClient, auth_headers: HeadersFor, sample_admin: Actor):
    response = client.get("/me", headers=auth_headers(sample_admin))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["org"]["name"] == "Acme"
