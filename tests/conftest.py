"""Pytest fixtures and configuration."""

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

# Ensure tests use an in-memory or temporary sqlite database
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI test client with lifespan handling."""
    with TestClient(app) as test_client:
        yield test_client
