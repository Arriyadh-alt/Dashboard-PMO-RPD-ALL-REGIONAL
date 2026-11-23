import json
import secrets

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from tests.fixtures import encrypted_fixture, fixture_data


@pytest.fixture(scope="session")
def encrypted_source(tmp_path_factory):
    directory = tmp_path_factory.mktemp("synthetic-rpd")
    password = secrets.token_urlsafe(24)
    viewer_password = secrets.token_urlsafe(24)
    path = directory / "synthetic.enc.json"
    path.write_text(json.dumps(encrypted_fixture(fixture_data(), {
        "fixture-admin": (password, "a"), "fixture-viewer": (viewer_password, "g")})))
    return path, password, viewer_password


@pytest.fixture
def app(encrypted_source, tmp_path):
    return create_app(encrypted_source[0], tmp_path / "state", origin="http://testserver", dev=True)


@pytest.fixture
def client(app):
    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        yield client


@pytest.fixture
def signed(client, encrypted_source):
    def sign(role="owner"):
        name = "fixture-admin" if role == "owner" else "fixture-viewer"
        password = encrypted_source[1 if role == "owner" else 2]
        assert client.post("/api/login", json={"account": name, "password": password}).status_code == 200
        bootstrap = client.get("/api/bootstrap").json()
        client.headers["x-csrf-token"] = bootstrap["csrf"]
        return client, bootstrap
    return sign
