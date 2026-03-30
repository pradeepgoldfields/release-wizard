import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_liveness(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_readiness(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
