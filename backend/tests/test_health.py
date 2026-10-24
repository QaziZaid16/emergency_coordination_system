def test_liveness_and_database_readiness(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


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
