"""Initial tests verifying application imports and health check endpoint."""

from fastapi.testclient import TestClient


def test_import_application() -> None:
    """Verify core application modules can be imported without error."""
    import app.main
    import app.agent.model
    import app.agent.instructions
    import app.agent.agent
    import app.tools
    import app.workflow
    import app.storage.database
    import app.api.routes

    assert app.main.app is not None
    assert app.main.app.title == "AI Operations Agent"


def test_health_endpoint(client: TestClient) -> None:
    """Verify that the health check endpoint returns 200 OK and expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-operations-agent"
    assert "version" in data


def test_root_endpoint(client: TestClient) -> None:
    """Verify that the root metadata endpoint returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Operations Agent"
