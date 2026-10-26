import logging

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError


def test_liveness_and_database_readiness(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_readiness_reports_sanitized_database_outage(monkeypatch, caplog):
    from app import main

    secret_detail = "synthetic-db-error-must-not-be-logged"

    def unavailable_connection():
        raise OperationalError("SELECT 1", {}, RuntimeError(secret_detail))

    monkeypatch.setattr(main.engine, "connect", unavailable_connection)
    with caplog.at_level(logging.WARNING, logger="app.main"):
        with pytest.raises(HTTPException) as error:
            main.ready()

    assert error.value.status_code == 503
    assert error.value.detail == "Database unavailable"
    assert secret_detail not in caplog.text
    assert "OperationalError" in caplog.text


def test_dashboard_preflight_allows_responder_capability_updates(client):
    response = client.options(
        "/api/v1/admin/responders/responder-id/capabilities",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
