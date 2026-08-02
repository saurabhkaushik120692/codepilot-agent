"""Tests for the ACP Server."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from codepilot.acp_server import app, set_orchestrator

    mock_orch = AsyncMock()
    mock_orch.handle_message.return_value.success = True
    set_orchestrator(mock_orch)

    return TestClient(app)


class TestACPHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestACPSubmitTask:
    def test_submit_task(self, client):
        response = client.post(
            "/tasks",
            json={"description": "Fix the bug", "issue_number": 42},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "TRIAGED"


class TestACPTaskStatus:
    def test_get_unknown_task(self, client):
        response = client.get("/tasks/nonexistent")
        assert response.status_code == 404

    def test_get_task_after_submit(self, client):
        resp = client.post("/tasks", json={"description": "Test"})
        task_id = resp.json()["task_id"]

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["description"] == "Test"

    def test_get_task_result(self, client):
        resp = client.post("/tasks", json={"description": "Test"})
        task_id = resp.json()["task_id"]

        response = client.get(f"/tasks/{task_id}/result")
        assert response.status_code == 200
        assert response.json()["status"] == "TRIAGED"
